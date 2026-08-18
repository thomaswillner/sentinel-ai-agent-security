from pathlib import Path

from sasb.build.svg import load_diagrams, render_svg
from sasb.i18n import LOCALES, load_locale
from sasb.model import load_entities

ENTITIES = {e.id: e for e in load_entities(Path("model/entities.yaml"))}
FIGURES = load_diagrams(Path("model/diagram.yaml"))


def test_all_three_figures_defined():
    assert {f.id for f in FIGURES} == {
        "reference-architecture", "prompt-injection-flow", "session-reconstruction"}


def test_svg_is_standalone_and_uses_absolute_text_positions():
    svg = render_svg(FIGURES[0], ENTITIES, load_locale("en"))
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    # <tspan> and relative offsets collapse when imported into vector editors.
    assert "<tspan" not in svg
    # librsvg does not resolve custom properties; a var()-based fill renders black.
    assert "var(--" not in svg


def test_element_ids_are_unique_across_every_figure_and_locale():
    import re
    ids = []
    for locale in LOCALES:
        loc = load_locale(locale)
        for fig in FIGURES:
            ids += re.findall(r'id="([^"]+)"', render_svg(fig, ENTITIES, loc))
    assert len(ids) == len(set(ids)), "duplicate ids break url(#...) references"


def test_render_is_deterministic():
    loc = load_locale("en")
    assert render_svg(FIGURES[0], ENTITIES, loc) == render_svg(FIGURES[0], ENTITIES, loc)
