"""Classify a Microsoft Learn page into a drift verdict.

`classify` is pure so the detector can be driven by known-bad fixtures. A
detector that has only ever seen healthy pages has not been shown to work.

Detection is *scoped*, not whole-page. The Sentinel connector reference is a
1.7 MB document listing hundreds of connectors, several of them genuinely
deprecated, so a naive page-wide grep for "deprecated" would flag every entity
pinned to it. Instead the search is narrowed to a window around the entity's
own name, and for tables and connectors the disappearance of that name is
itself the signal.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .http_evidence import FetchResult, fetch
from .model import Entity
from .verdicts import Verdict

DEPRECATION_PATTERNS = (
    r"\bdeprecat\w*",
    r"\bretir(?:e|ed|ement|ing)\b",
    r"\bwill be removed\b",
    r"\bno longer the recommended\b",
    r"\bsupersed\w*",
    r"\bend of support\b",
)
_DEPRECATION_RE = re.compile("|".join(DEPRECATION_PATTERNS), re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_STRIP_RE = re.compile(
    r"<(script|style|nav|footer|header)\b.*?</\1>", re.IGNORECASE | re.DOTALL
)
_MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_PREVIEW_RE = re.compile(r"\bis currently in preview\b|\bin preview\b", re.IGNORECASE)
#: Microsoft Learn renders callouts as <div class="IMPORTANT"> etc. Only these
#: three carry page-level status warnings; NOTE and TIP are ordinary asides.
_CALLOUT_RE = re.compile(
    r'<div class="(IMPORTANT|WARNING|CAUTION)">(.*?)</div>', re.IGNORECASE | re.DOTALL
)

#: Characters of context searched either side of the entity name.
SCOPE_RADIUS = 1500
#: Kinds whose name vanishing from its page means the thing is gone.
NAME_REQUIRED_KINDS = frozenset({"table", "connector"})
#: Microsoft Learn locale path segments.
LOCALE_SEGMENTS = {"en": "en-us", "de": "de-de"}


@dataclass(frozen=True)
class Probe:
    entity_id: str
    verdict: Verdict
    title: str | None
    status_detected: str | None
    final_url: str
    fingerprint: str
    evidence: list[str] = field(default_factory=list)


def _text_of(body: str) -> str:
    """Visible main-content text, with chrome removed."""
    cleaned = _STRIP_RE.sub(" ", body)
    main = _MAIN_RE.search(cleaned)
    inner = main.group(1) if main else cleaned
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", inner)).strip()


def _title(body: str) -> str | None:
    m = _TITLE_RE.search(body)
    if not m:
        return None
    return _TAG_RE.sub("", m.group(1)).split("|")[0].strip()


def _normalise(url: str) -> str:
    return url.rstrip("/").split("?")[0].removeprefix("https://learn.microsoft.com")


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.lower().encode("utf-8")).hexdigest()[:16]


def _callout_text(body: str) -> str:
    """Text of the page's IMPORTANT/WARNING/CAUTION callouts only.

    Deprecation is detected here rather than in body prose. A text window around
    an entity name cannot tell whose deprecation it is reading: on the Agent 365
    concepts page the sentence "no longer the recommended path" belongs to the
    SDK, and window-based matching wrongly attributed it to Agent 365 itself.
    A callout is a structural signal, so it needs no subject inference.
    """
    parts = [inner for _, inner in _CALLOUT_RE.findall(body)]
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", " ".join(parts))).strip()


def _scope(text: str, needle: str) -> str | None:
    """Window of text around the first occurrence of `needle`, or None."""
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return None
    return text[max(0, idx - SCOPE_RADIUS) : idx + len(needle) + SCOPE_RADIUS]


def classify(entity: Entity, result: FetchResult, *, shared_page: bool = False) -> Probe:
    text = _text_of(result.body)

    def mk(verdict, evidence, title=None, status=None) -> Probe:
        return Probe(entity.id, verdict, title, status, result.final_url,
                     _fingerprint(text), evidence)

    if result.status in (404, 410):
        return mk(Verdict.NOT_FOUND, [f"HTTP {result.status} at {entity.learn_url}"])
    if not result.ok:
        return mk(Verdict.UNREACHABLE, [result.error or f"HTTP {result.status}"])

    title = _title(result.body)
    needle = entity.match_target
    scope = _scope(text, needle)

    if scope is None and entity.kind in NAME_REQUIRED_KINDS and not entity.article_claim:
        return mk(Verdict.NOT_FOUND,
                  [f"{needle!r} no longer appears on its documentation page"],
                  title)

    # On a page documenting many products -- the Sentinel connector reference
    # lists hundreds -- a callout belongs to some connector, not necessarily
    # this one. Attributing it here would repeat the wrong-subject error one
    # level up, so shared pages must assert supersession explicitly instead.
    callouts = "" if shared_page else _callout_text(result.body)
    hits = sorted({m.group(0).lower() for m in _DEPRECATION_RE.finditer(callouts)})
    if hits:
        return mk(Verdict.DEPRECATED,
                  [f"deprecation notice in a page callout: {hits[:5]}"],
                  title, "superseded")

    haystack = scope if scope is not None else text

    if _normalise(result.final_url) != _normalise(entity.learn_url):
        return mk(Verdict.RENAMED, [f"redirected to {result.final_url}"], title)

    if scope is None:
        if entity.article_claim:
            return mk(Verdict.CHANGED,
                      [f"{needle!r} does not appear in current Microsoft documentation; "
                       "the article's wording no longer matches what Microsoft documents"],
                      title, "documented-differently")
        return mk(Verdict.RENAMED,
                  [f"{needle!r} not found in page text; wording may have changed"],
                  title)

    status = "preview" if _PREVIEW_RE.search(haystack) else "ga"
    if status != entity.expected_status:
        return mk(Verdict.CHANGED,
                  [f"status reads {status}, model expects {entity.expected_status}"],
                  title, status)

    return mk(Verdict.CURRENT, ["present, named and status as expected"], title, status)


def localized_url(url: str, locale: str) -> str:
    """Swap the Learn locale segment. Existence is verified, never assumed."""
    return url.replace("/en-us/", f"/{LOCALE_SEGMENTS[locale]}/")


def verify_localized(url: str, locale: str) -> str | None:
    """Return the localized URL if it genuinely serves that locale, else None.

    Learn silently falls back to English for untranslated pages, so a 200 alone
    is not proof of a translation -- the final URL must still carry the locale.
    """
    if locale == "en":
        return url
    candidate = localized_url(url, locale)
    result = fetch(candidate, timeout=25)
    segment = f"/{LOCALE_SEGMENTS[locale]}/"
    if result.ok and segment in result.final_url:
        return result.final_url
    return None


def check_deprecation_assertion(entity: Entity) -> tuple[bool, str]:
    """Verify an explicitly pinned supersession statement.

    Some supersessions are documented on a different page from the thing being
    superseded -- the Agent 365 SDK is declared "no longer the recommended path"
    on the concepts page, not on its own. Pinning the exact page and phrase turns
    that from an inference about prose into an assertion the sweep verifies.
    """
    probe_spec = entity.deprecation_probe or {}
    url, phrase = probe_spec.get("url"), probe_spec.get("phrase")
    if not url or not phrase:
        return False, ""
    result = fetch(url)
    if not result.ok:
        return False, f"supersession source unreachable: {result.error}"
    present = phrase.lower() in _text_of(result.body).lower()
    return present, (f"documented at {url}: {phrase!r}" if present
                     else f"pinned supersession phrase absent from {url}")


def probe(entity: Entity, *, shared_page: bool = False) -> Probe:
    result = classify(entity, fetch(entity.learn_url), shared_page=shared_page)
    if entity.deprecation_probe and result.verdict is not Verdict.DEPRECATED:
        confirmed, note = check_deprecation_assertion(entity)
        if confirmed:
            return Probe(entity.id, Verdict.DEPRECATED, result.title, "superseded",
                         result.final_url, result.fingerprint, [note])
        return Probe(entity.id, Verdict.CHANGED, result.title, result.status_detected,
                     result.final_url, result.fingerprint,
                     [note or "supersession no longer documented as pinned"])
    return result
