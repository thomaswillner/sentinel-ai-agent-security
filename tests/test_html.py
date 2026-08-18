import json
from pathlib import Path

from sasb.build.html import load_content, render_html
from sasb.build.svg import load_diagrams
from sasb.i18n import LOCALES, load_locale
from sasb.model import load_entities

RECON = json.loads(Path("state/reconciliation.json").read_text(encoding="utf-8"))


def _render() -> str:
    return render_html(
        load_content(Path("model/content.yaml")),
        {e.id: e for e in load_entities(Path("model/entities.yaml"))},
        load_diagrams(Path("model/diagram.yaml")),
        RECON,
        {name: load_locale(name) for name in LOCALES},
    )


def test_render_is_deterministic():
    assert _render() == _render()


def test_carries_attribution_and_reconciliation_time():
    html = _render()
    assert RECON["article"]["author"] in html
    assert RECON["checked_at"] in html
    assert "techcommunity.microsoft.com" in html


def test_every_entity_appears_with_verdict_and_source():
    html = _render()
    for row in RECON["entities"]:
        assert row["name"] in html
        assert row["source_urls"]["en"] in html


def test_both_languages_present():
    html = _render()
    assert 'data-langroot="en"' in html and 'data-langroot="de"' in html
    assert "Eine neue Angriffsfläche" in html and "A new attack surface" in html


def test_has_print_styles_and_export_links():
    html = _render()
    assert "@media print" in html
    for name in LOCALES:
        assert f'href="brief.{name}.pdf" download' in html
        assert f'href="brief.{name}.pptx" download' in html


def test_figures_are_clickable_and_saveable():
    html = _render()
    assert 'data-entity="unified-agent-observability"' in html
    assert 'href="reference-architecture.en.svg" download' in html
    assert 'href="reference-architecture.en@4x.png" download' in html


def test_refuses_to_publish_an_unknown_state():
    import pytest
    from sasb.verdicts import Verdict, assert_publishable
    with pytest.raises(ValueError, match="not a known state"):
        assert_publishable([Verdict.CURRENT, Verdict.NOT_FOUND])


def test_unresolvable_token_fails_the_build():
    import pytest
    from sasb.build.html import assert_tokens_resolve
    ents = {e.id: e for e in load_entities(Path("model/entities.yaml"))}
    poisoned = {"en": {"sections": {"intro": {"body": ["See {no-such-product} today."]}}}}
    with pytest.raises(ValueError, match="unresolvable entity tokens"):
        assert_tokens_resolve(poisoned, ents)


def test_prose_is_bound_to_the_model_not_hardcoded():
    """A rename in entities.yaml must move the prose with it."""
    from sasb.build.html import resolve_tokens
    ents = {e.id: e for e in load_entities(Path("model/entities.yaml"))}
    assert resolve_tokens("built on {foundry}", ents) == "built on Microsoft Foundry"
    html = _render()
    # The article's wording must not be hardcoded into the body prose.
    assert "Azure AI Foundry Agents" not in html.split('class="recon"')[0]


def test_covers_the_source_article_specifics():
    """Regression guard: the brief must not silently thin out the post."""
    html = _render()
    for term in ("query_lake", "RunAdvancedHuntingQuery", "ServiceNow", "SharePoint",
                 "Graph API", "MCP", "developer mode", "system prompt",
                 "Most active agents", "High-risk MCP tools",
                 "Agent ownership analysis", "SCStelz"):
        assert term.lower() in html.lower(), f"article specific missing: {term}"


def test_links_are_styled_not_browser_default():
    """A page with a dark theme must never fall through to UA link blue.

    Measured on the live page before this test existed: 23 links rendered
    rgb(0,0,238) against a rgb(13,17,26) background -- about 1.3:1 contrast.
    """
    from sasb.build.html import CSS
    assert "--link:" in CSS, "no link colour token defined"
    assert "a{color:var(--link)" in CSS.replace(" ", ""), "no global anchor colour rule"
    light, dark = CSS.split("@media (prefers-color-scheme:dark)", 1)
    assert "--link:" in light, "link colour missing from the light palette"
    assert "--link:" in dark, "link colour missing from the dark palette"


def test_enlarged_figure_uses_the_whole_viewport():
    """Enlarge must actually enlarge.

    Measured before this test: inline 1110x596 vs lightbox 1316x707 at a
    1440x900 viewport -- a 19% gain, which reads as 'nothing happened'.
    """
    from sasb.build.html import CSS
    flat = CSS.replace(" ", "").replace("\n", "")
    assert "width:100vw" in flat and "height:100vh" in flat, "wide dialog is not full-viewport"
    assert "max-width:none" in flat, "wide dialog still capped by max-width"
