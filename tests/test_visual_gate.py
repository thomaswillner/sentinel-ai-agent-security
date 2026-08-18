"""G4: the generated figure must survive rendering, not merely validate.

This gate exists because a var()-based stylesheet produced a structurally valid
SVG that librsvg rasterised as a solid black rectangle. Schema checks passed it;
OCR did not.
"""
from pathlib import Path

import pytest

from sasb.build.svg import load_diagrams, render_svg
from sasb.gates.visual import check
from sasb.i18n import load_locale
from sasb.model import load_entities

OFFCANVAS = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120" '
    'viewBox="0 0 400 120"><rect width="400" height="120" fill="#fff"/>'
    '<text x="-9000" y="60" font-size="16" fill="#000">CloudAppEvents</text></svg>'
)


def _figure(fig_id: str, locale: str) -> str:
    entities = {e.id: e for e in load_entities(Path("model/entities.yaml"))}
    figures = load_diagrams(Path("model/diagram.yaml"))
    return render_svg(next(f for f in figures if f.id == fig_id),
                      entities, load_locale(locale))


@pytest.mark.parametrize("locale,tokens", [
    ("en", ["Microsoft Sentinel", "CloudAppEvents", "Data Connectors"]),
    ("de", ["Microsoft Sentinel", "CloudAppEvents", "Datenconnectoren"]),
])
def test_reference_architecture_is_legible_when_rendered(tmp_path, locale, tokens):
    svg = tmp_path / f"fig.{locale}.svg"
    svg.write_text(_figure("reference-architecture", locale), encoding="utf-8")
    passed, missing = check(svg, tokens)
    assert passed, f"OCR could not read {missing} from the rendered figure"


def test_offcanvas_text_fails_the_gate(tmp_path):
    bad = tmp_path / "bad.svg"
    bad.write_text(OFFCANVAS, encoding="utf-8")
    passed, missing = check(bad, ["CloudAppEvents"])
    assert not passed and "CloudAppEvents" in missing
