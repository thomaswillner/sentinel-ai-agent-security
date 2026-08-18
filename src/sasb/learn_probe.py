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
    r"\bdiscontinu\w*",
    r"\bobsolete\b",
    r"\breplaced by\b",
)
_DEPRECATION_RE = re.compile("|".join(DEPRECATION_PATTERNS), re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_STRIP_RE = re.compile(
    r"<(script|style|nav|footer|header)\b.*?</\1>", re.IGNORECASE | re.DOTALL
)
_MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_PREVIEW_RE = re.compile(
    r"(?<!no longer )(?<!not )\bis currently in preview\b"
    r"|(?<!no longer )(?<!not )\bin preview\b", re.IGNORECASE)
#: Microsoft Learn renders callouts as <div class="IMPORTANT"> etc. Only these
#: three carry page-level status warnings; NOTE and TIP are ordinary asides.
_CALLOUT_OPEN_RE = re.compile(r'<div class="(IMPORTANT|WARNING|CAUTION)">',
                              re.IGNORECASE)
_DIV_RE = re.compile(r"<div\b[^>]*>|</div>", re.IGNORECASE)

#: Sentence boundaries used to bind a deprecation claim to its subject.
#: Emitted where a block-level element ends, so a heading cannot glue onto the
#: paragraph beneath it and lend its name to another subject's sentence.
#: \x1f is the obvious sentinel, but Python counts the separator control
#: characters as whitespace, so the collapse in _text_of erased it.
BLOCK_MARK = "\x01"
_BLOCK_RE = re.compile(
    r"</(?:h[1-6]|p|li|div|tr|td|th|section|figcaption|blockquote)>|<br\s*/?>",
    re.IGNORECASE)
#: Sentence boundaries used to bind a deprecation claim to its subject. Dashes
#: are intra-sentence punctuation -- splitting on them severed "Foo connector --
#: retired" into a name fragment and a verb fragment.
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+|" + BLOCK_MARK)
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
    inner = _BLOCK_RE.sub(BLOCK_MARK, inner)
    flat = re.sub(r"[^\S\n]+", " ", _TAG_RE.sub(" ", inner))
    return re.sub(r"\s*\n\s*", " ", flat).strip()


def _title(body: str) -> str | None:
    m = _TITLE_RE.search(body)
    if not m:
        return None
    return _TAG_RE.sub("", m.group(1)).split("|")[0].strip()


def _normalise(url: str) -> str:
    return url.rstrip("/").split("?")[0].removeprefix("https://learn.microsoft.com")


def _fingerprint(text: str) -> str:
    clean = " ".join(text.replace(BLOCK_MARK, " ").split()).lower()
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


def _callout_text(body: str) -> str:
    """Text of the page's IMPORTANT/WARNING/CAUTION callouts only.

    Deprecation is detected here rather than in body prose. A text window around
    an entity name cannot tell whose deprecation it is reading: on the Agent 365
    concepts page the sentence "no longer the recommended path" belongs to the
    SDK, and window-based matching wrongly attributed it to Agent 365 itself.
    A callout is a structural signal, so it needs no subject inference.
    """
    parts: list[str] = []
    for match in _CALLOUT_OPEN_RE.finditer(body):
        # Walk div open/close tags to the matching close. A non-greedy
        # ".*?</div>" stops at the first nested close -- on a real Learn callout
        # that is the icon div, so the entire notice was silently discarded.
        depth, pos = 1, match.end()
        for tag in _DIV_RE.finditer(body, match.end()):
            depth += -1 if tag.group(0).lower() == "</div>" else 1
            if depth == 0:
                parts.append(body[pos:tag.start()])
                break
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", " ".join(parts))).strip()


def _scope(text: str, needle: str) -> str | None:
    """Window of text around the first occurrence of `needle`, or None."""
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return None
    return text[max(0, idx - SCOPE_RADIUS) : idx + len(needle) + SCOPE_RADIUS]


def _self_referential_deprecation(text: str, needle: str) -> str | None:
    """A deprecation sentence whose subject is this entity.

    Proximity is not enough and never will be: "The earlier SDK is no longer the
    recommended path" sits centimetres from "Agent 365" and is about something
    else, and a neighbouring row's retirement notice sits inside any window wide
    enough to be useful. Both were shipped as false positives.

    The rule here is co-occurrence inside a single sentence: the entity's own
    name and the deprecation language must appear together. "Foo connector --
    retired" fires; "This feature is deprecated" does not, because it never says
    which feature. Abstaining when the evidence does not name its subject is the
    correct behaviour -- a pinned deprecation_probe covers those cases exactly.
    """
    for sentence in _SENTENCE_RE.split(text):
        if needle.lower() not in sentence.lower():
            continue
        match = _DEPRECATION_RE.search(sentence)
        if match:
            return " ".join(sentence.split())[:200]
    return None


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
    # Measured once, up front, so every verdict that came from a real read
    # carries a real availability. Leaving it None on the RENAMED paths meant
    # reconcile had to invent one.
    # Only the entity's own scope may supply its availability. Falling back to
    # the whole page let a neighbouring product's "(in preview)" be published as
    # this entity's measurement on a page listing hundreds of connectors.
    observed_status = ("unknown" if scope is None
                       else "preview" if _PREVIEW_RE.search(scope) else "ga")

    if scope is None and entity.kind in NAME_REQUIRED_KINDS and not entity.article_claim:
        return mk(Verdict.NOT_FOUND,
                  [f"{needle!r} no longer appears on its documentation page"],
                  title)

    # On a page documenting many products -- the Sentinel connector reference
    # lists hundreds -- a callout belongs to some connector, not necessarily
    # this one. Attributing it here would repeat the wrong-subject error one
    # level up, so shared pages must assert supersession explicitly instead.
    # Two evidence sources, each scoped so the signal cannot be attributed to
    # the wrong subject. On a page shared by many products a callout belongs to
    # some product, not necessarily this one, so only the entity's own text
    # block counts there. Removing the signal entirely (the previous fix)
    # traded false positives for false negatives.
    # A callout can be about a sub-feature, a legacy API, or a portal
    # experience rather than the product itself, and shared_page is decided by
    # our watchlist rather than by the page. So a callout flags for review; it
    # does not assert. Only an explicit pinned deprecation_probe asserts.
    if not shared_page:
        callout_hits = sorted({m.group(0).lower()
                               for m in _DEPRECATION_RE.finditer(_callout_text(result.body))})
        if callout_hits:
            return mk(Verdict.CHANGED,
                      ["deprecation language in a page callout, needs review: "
                       f"{callout_hits[:5]}"],
                      title, "review-needed")

    # Inline prose FLAGS, it never asserts. Even same-sentence co-occurrence
    # cannot tell "X is retired" from "X in the Azure portal is retired" -- the
    # second fired against Microsoft Sentinel itself, which is not retiring.
    # Every attempt to separate those by pattern has produced a new construct
    # that defeats it, so the honest output is a review flag. A structural
    # callout, or an explicit pinned deprecation_probe, is what publishes
    # DEPRECATED as a fact.
    sentence = _self_referential_deprecation(text, needle)
    if sentence:
        return mk(Verdict.CHANGED,
                  ["possible deprecation language, needs review: "
                   f"{sentence!r}"],
                  title, "review-needed")

    haystack = scope if scope is not None else text

    if _normalise(result.final_url) != _normalise(entity.learn_url):
        return mk(Verdict.RENAMED, [f"redirected to {result.final_url}"], title,
                  observed_status)

    if scope is None:
        if entity.article_claim:
            return mk(Verdict.CHANGED,
                      [f"{needle!r} does not appear in current Microsoft documentation; "
                       "the article's wording no longer matches what Microsoft documents"],
                      title, "documented-differently")
        return mk(Verdict.RENAMED,
                  [f"{needle!r} not found in page text; wording may have changed"],
                  title, observed_status)

    status = observed_status
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


def check_deprecation_assertion(entity: Entity) -> tuple[bool, str, bool]:
    """Verify an explicitly pinned supersession statement.

    Some supersessions are documented on a different page from the thing being
    superseded -- the Agent 365 SDK is declared "no longer the recommended path"
    on the concepts page, not on its own. Pinning the exact page and phrase turns
    that from an inference about prose into an assertion the sweep verifies.
    """
    probe_spec = entity.deprecation_probe or {}
    url, phrase = probe_spec.get("url"), probe_spec.get("phrase")
    if not url or not phrase:
        return False, f"malformed deprecation_probe on {entity.id}", False
    result = fetch(url)
    if not result.ok:
        return False, f"supersession source unreachable: {result.error}", False
    present = phrase.lower() in _text_of(result.body).lower()
    return present, (f"documented at {url}: {phrase!r}" if present
                     else f"pinned supersession phrase absent from {url}"), True


#: Verdicts that mean the entity's own page was actually read.
MEASURED = frozenset({Verdict.CURRENT, Verdict.CHANGED, Verdict.RENAMED,
                      Verdict.DEPRECATED})


def probe(entity: Entity, *, shared_page: bool = False) -> Probe:
    result = classify(entity, fetch(entity.learn_url), shared_page=shared_page)
    # A pinned supersession check may only refine a verdict that came from an
    # actual read. Running it after UNREACHABLE or NOT_FOUND would replace a
    # failed measurement with a published claim about a page never seen.
    if result.verdict not in MEASURED:
        return result
    if entity.deprecation_probe and result.verdict is not Verdict.DEPRECATED:
        confirmed, note, reachable = check_deprecation_assertion(entity)
        if not reachable:
            # The pin could not be read. Converting that into CHANGED published
            # a drift verdict whose only evidence was a network error string.
            return Probe(entity.id, Verdict.UNREACHABLE, result.title, "unknown",
                         result.final_url, result.fingerprint, [note])
        if confirmed:
            return Probe(entity.id, Verdict.DEPRECATED, result.title, "superseded",
                         result.final_url, result.fingerprint, [note])
        return Probe(entity.id, Verdict.CHANGED, result.title, result.status_detected,
                     result.final_url, result.fingerprint,
                     [note or "supersession no longer documented as pinned"])
    return result
