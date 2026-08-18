from pathlib import Path

from sasb.http_evidence import FetchResult
from sasb.learn_probe import classify
from sasb.model import Entity
from sasb.verdicts import Verdict

FIX = Path(__file__).parent / "fixtures"
URL = "https://learn.microsoft.com/en-us/azure/sentinel/overview"
SUMMARY = "Fixture entity used to prove the drift detector reacts to known-bad pages."


def _entity(**kw) -> Entity:
    base = dict(id="sentinel", name="Microsoft Sentinel", kind="platform",
                learn_url=URL, expected_status="ga", summary=SUMMARY)
    base.update(kw)
    return Entity(**base)


def _result(fixture: str, status: int = 200, final: str | None = None) -> FetchResult:
    return FetchResult(URL, final or URL, status, (FIX / fixture).read_text())


def test_healthy_page_is_current():
    assert classify(_entity(), _result("learn_ok.html")).verdict is Verdict.CURRENT


def test_chrome_deprecation_language_does_not_false_positive():
    # nav/footer mention deprecation; only main content near the name counts.
    assert classify(_entity(), _result("learn_ok.html")).verdict is not Verdict.DEPRECATED


def test_planted_deprecation_banner_is_flagged():
    """A callout is evidence worth surfacing, but it is not an assertion.

    It may describe a sub-feature, a legacy API or a portal experience rather
    than the product the page is about, so it raises review rather than
    publishing DEPRECATED as fact.
    """
    p = classify(_entity(), _result("learn_deprecated.html"))
    assert p.verdict is not Verdict.CURRENT
    assert any("deprecat" in e.lower() or "retir" in e.lower() for e in p.evidence)
    assert "needs review" in " ".join(p.evidence)


def test_only_a_pinned_probe_asserts_deprecation():
    """The single path allowed to publish DEPRECATED as a fact."""
    from sasb.learn_probe import probe
    import sasb.learn_probe as lp, importlib

    ent = _entity(id="sdk", deprecation_probe={
        "url": "https://learn.microsoft.com/en-us/pin",
        "phrase": "no longer the recommended path"})
    healthy = ('<html><head><title>Microsoft Sentinel</title></head><body><main>'
               '<h1>Microsoft Sentinel</h1><p>All well.</p></main></body></html>')
    pinned = ('<html><body><main><p>The earlier tool is no longer the recommended '
              'path for new integrations.</p></main></body></html>')

    lp.fetch = lambda url, timeout=30: FetchResult(
        url, url, 200, pinned if url.endswith("/pin") else healthy)
    try:
        result = probe(ent)
    finally:
        importlib.reload(lp)
    assert result.verdict is Verdict.DEPRECATED
    assert result.status_detected == "superseded"


def test_title_and_name_change_is_renamed():
    assert classify(_entity(), _result("learn_renamed_title.html")).verdict is Verdict.RENAMED


def test_redirect_to_different_path_is_renamed():
    p = classify(_entity(), _result(
        "learn_ok.html",
        final="https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry"))
    assert p.verdict is Verdict.RENAMED


def test_vanished_table_name_is_not_found():
    ent = _entity(id="t", name="UnifiedAgentObservability", kind="table",
                  expected_status="preview")
    p = classify(ent, _result("learn_table_missing.html"))
    assert p.verdict is Verdict.NOT_FOUND


def test_404_is_not_found():
    p = classify(_entity(), FetchResult(URL, URL, 404, "", error="HTTP 404"))
    assert p.verdict is Verdict.NOT_FOUND


def test_503_is_unreachable_not_current():
    p = classify(_entity(), FetchResult(URL, URL, 503, "", error="HTTP 503"))
    assert p.verdict is Verdict.UNREACHABLE


def test_network_failure_is_unreachable():
    p = classify(_entity(), FetchResult(URL, URL, 0, "", error="URLError: boom"))
    assert p.verdict is Verdict.UNREACHABLE


def test_callout_on_a_shared_page_is_not_attributed_to_this_entity():
    # data-connectors-reference documents hundreds of connectors; a retirement
    # callout there belongs to some connector, not necessarily this one.
    p = classify(_entity(kind="connector", name="Microsoft Sentinel"),
                 _result("learn_deprecated.html"), shared_page=True)
    assert p.verdict is not Verdict.DEPRECATED


def test_body_prose_deprecation_is_not_a_deprecation():
    # "no longer the recommended path" about a *different* product must not
    # deprecate this entity. This is the Agent 365 false positive.
    body = ('<html><head><title>Microsoft Sentinel | Microsoft Learn</title></head><body><main>'
            '<h1>Microsoft Sentinel</h1><p>The earlier SDK is no longer the recommended '
            'path for new integrations.</p></main></body></html>')
    p = classify(_entity(), FetchResult(URL, URL, 200, body))
    assert p.verdict is not Verdict.DEPRECATED


# --- regressions from the glm-5.3 adversarial review (2026-08-18) ---

def test_unreachable_is_not_laundered_by_a_deprecation_probe():
    """CRITICAL 1: a pinned supersession check must not overwrite a failed read."""
    from sasb.learn_probe import Probe, probe
    import sasb.learn_probe as lp

    ent = _entity(id="sdk", deprecation_probe={
        "url": "https://learn.microsoft.com/en-us/x", "phrase": "no longer recommended"})
    calls = []
    lp.fetch = lambda url, timeout=30: (calls.append(url) or
                                        FetchResult(url, url, 0, "", error="URLError: boom"))
    try:
        result = probe(ent)
    finally:
        import importlib
        importlib.reload(lp)
    assert result.verdict is Verdict.UNREACHABLE, (
        "an entity whose own page could not be read must stay UNREACHABLE")


def test_nested_callout_markup_is_not_truncated():
    """HIGH 5: Learn callouts carry nested markup; the icon div ate the text."""
    from sasb.learn_probe import _callout_text
    nested = ('<div class="IMPORTANT"><div class="icon"></div>'
              '<p>The Foo connector is retired.</p></div>')
    assert "retired" in _callout_text(nested).lower()


def test_inline_deprecation_is_flagged_for_review_not_asserted():
    """HIGH 5: a retired row must not read CURRENT, but prose cannot assert.

    "Microsoft Sentinel in the Azure portal retirement timeline" names the
    entity and a retirement in one sentence, yet Sentinel is not retiring -- the
    portal experience is. Inline evidence therefore flags; only a structural
    callout or a pinned probe publishes DEPRECATED.
    """
    body = ('<html><head><title>Foo connector</title></head><body><main>'
            '<h1>Foo connector</h1><p>Foo connector — retired. Use Bar instead.</p>'
            '</main></body></html>')
    ent = _entity(id="foo", name="Foo connector", kind="connector")
    probe_result = classify(ent, FetchResult(URL, URL, 200, body))
    assert probe_result.verdict is not Verdict.CURRENT
    assert "needs review" in " ".join(probe_result.evidence)


def test_a_qualified_retirement_does_not_deprecate_the_product():
    """The Azure-portal retirement must not mark Microsoft Sentinel deprecated."""
    body = ('<html><head><title>Microsoft Sentinel</title></head><body><main>'
            '<h1>Microsoft Sentinel</h1>'
            '<p>Microsoft Sentinel in the Azure portal retirement timeline</p>'
            '</main></body></html>')
    result = classify(_entity(), FetchResult(URL, URL, 200, body))
    assert result.verdict is not Verdict.DEPRECATED


# --- regressions from the second glm-5.3 review ---

def test_unreachable_pinned_probe_is_inconclusive_not_drift():
    """An unreachable pin must not become a published CHANGED verdict."""
    from sasb.learn_probe import probe
    import sasb.learn_probe as lp, importlib

    ent = _entity(id="sdk", deprecation_probe={
        "url": "https://learn.microsoft.com/en-us/pin", "phrase": "no longer recommended"})
    healthy = ('<html><head><title>Microsoft Sentinel</title></head><body><main>'
               '<h1>Microsoft Sentinel</h1><p>All well.</p></main></body></html>')

    def fake_fetch(url, timeout=30):
        if url.endswith("/pin"):
            return FetchResult(url, url, 0, "", error="URLError: timeout")
        return FetchResult(url, url, 200, healthy)

    lp.fetch = fake_fetch
    try:
        result = probe(ent)
    finally:
        importlib.reload(lp)
    assert result.verdict is Verdict.UNREACHABLE


def test_callouts_flag_but_never_assert_deprecation():
    """Only a pinned probe may assert. A callout can be about a sub-feature."""
    body = ('<html><head><title>Microsoft Sentinel</title></head><body><main>'
            '<h1>Microsoft Sentinel</h1><div class="content"><div class="WARNING">'
            '<div class="icon"></div><p>The legacy API is retired.</p></div></div>'
            '</main></body></html>')
    result = classify(_entity(), FetchResult(URL, URL, 200, body))
    assert result.verdict is not Verdict.DEPRECATED
    assert result.verdict is not Verdict.CURRENT


def test_one_sentence_comparator_does_not_assert():
    """'Agent 365 supersedes the earlier SDK' must not deprecate Agent 365."""
    body = ('<html><head><title>Microsoft Sentinel</title></head><body><main>'
            '<h1>Microsoft Sentinel</h1><p>Microsoft Sentinel supersedes the earlier '
            'tool, which is no longer the recommended path.</p></main></body></html>')
    assert classify(_entity(), FetchResult(URL, URL, 200, body)).verdict is not Verdict.DEPRECATED


def test_no_longer_in_preview_is_not_preview():
    body = ('<html><head><title>Microsoft Sentinel</title></head><body><main>'
            '<h1>Microsoft Sentinel</h1><p>Microsoft Sentinel is no longer in preview.</p>'
            '</main></body></html>')
    result = classify(_entity(), FetchResult(URL, URL, 200, body))
    assert result.status_detected != "preview"


def test_absent_name_does_not_borrow_a_neighbours_status():
    """With no scope, status must not be read from the whole page."""
    body = ('<html><head><title>Connectors</title></head><body><main>'
            '<h1>Connectors</h1><p>Some Other Product (in preview) is listed here.</p>'
            '</main></body></html>')
    ent = _entity(id="gone", name="Vanished Thing", kind="platform")
    result = classify(ent, FetchResult(URL, URL, 200, body))
    assert result.status_detected != "preview", "borrowed a neighbour's availability"
