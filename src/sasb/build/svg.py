"""Generate the article's figures from the canonical model.

The figures are recreated, never copied. Structure lives in model/diagram.yaml
and every visible string resolves through model/i18n/<locale>.yaml, so the same
model renders both languages.

Two rendering rules matter downstream:

* Every visible line is one <text> element with an absolute numeric y. Relative
  offsets and <tspan> collapse when the SVG is imported into vector editors.
* Colours are CSS custom properties defined on :root and redefined under
  prefers-color-scheme: dark, so a single file works in both themes.

This module is pure: no network, no clock, no randomness.
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import yaml

from ..model import SCHEMA_DIR, Entity, ModelError

MARGIN = 26
GUTTER = 16
COL_HEAD_H = 52
CARD_PAD = 10
TITLE_SIZE = 13
CAPTION_SIZE = 10.5
LINE_H = 13
HEAD_SIZE = 15
#: Average glyph width as a fraction of font size, used for wrapping.
GLYPH_RATIO = 0.53


@dataclass(frozen=True)
class Figure:
    id: str
    width: int
    height: int
    columns: list[dict]
    bands: list[dict]
    steps: list[str]


def load_diagrams(path: Path) -> list[Figure]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    schema_path = SCHEMA_DIR / "diagram.schema.json"
    if schema_path.exists():
        validator = jsonschema.Draft202012Validator(
            json.loads(schema_path.read_text(encoding="utf-8"))
        )
        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errors:
            raise ModelError(f"diagram.schema.json: {errors[0].message}")
    figures = [
        Figure(
            id=f["id"],
            width=int(f["width"]),
            height=int(f["height"]),
            columns=list(f.get("columns") or []),
            bands=list(f.get("bands") or []),
            steps=list(f.get("steps") or []),
        )
        for f in doc["figures"]
    ]
    seen: set[str] = set()
    for fig in figures:
        if fig.id in seen:
            raise ModelError(f"duplicate figure id: {fig.id}")
        if not fig.columns and not fig.steps:
            raise ModelError(f"figure {fig.id} has neither columns nor steps")
        seen.add(fig.id)
    return figures


def wrap(text: str, width_px: float, size: float) -> list[str]:
    """Greedy wrap. Pure and deterministic -- no font metrics required."""
    limit = max(8, int(width_px / (size * GLYPH_RATIO)))
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


class _Canvas:
    """Accumulates SVG fragments in emission order."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    def add(self, fragment: str) -> None:
        self.parts.append(fragment)

    def text(self, x: float, y: float, content: str, cls: str,
             anchor: str = "start") -> None:
        fill, size, weight = TEXT[cls]
        anchor_attr = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" fill="{fill}" '
                 f'font-family="{FONT}" font-size="{size}" font-weight="{weight}"'
                 f"{anchor_attr}>{_esc(content)}</text>")

    def box(self, x: float, y: float, w: float, h: float, rx: float,
            cls: str, extra: str = "") -> None:
        fill, stroke = SHAPE[cls]
        stroke_attr = "" if stroke == "none" else f' stroke="{stroke}" stroke-width="1"'
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                 f'rx="{rx}" class="{cls}" fill="{fill}"{stroke_attr}{extra}/>')

    def lines(self, x: float, y: float, items: list[str], cls: str,
              line_h: float = LINE_H) -> float:
        for index, line in enumerate(items):
            self.text(x, y + index * line_h, line, cls)
        return y + len(items) * line_h


def _label(loc: dict, key: str, fallback: str = "") -> str:
    return (loc.get("diagram") or {}).get(key, fallback or key)


def _caption(loc: dict, entity_id: str) -> str:
    return ((loc.get("entities") or {}).get(entity_id) or {}).get("caption", "")


def _card_height(caption_lines: int) -> float:
    return CARD_PAD * 2 + TITLE_SIZE + 3 + caption_lines * LINE_H


def _render_columns(canvas: _Canvas, fig: Figure, entities: dict[str, Entity],
                    loc: dict, top: float, marker: str = "arrow") -> float:
    count = len(fig.columns)
    col_w = (fig.width - 2 * MARGIN - GUTTER * (count - 1)) / count
    inner_w = col_w - 2 * CARD_PAD - 12

    laid: list[list[tuple[Entity, list[str], float]]] = []
    for column in fig.columns:
        rows = []
        for entity_id in column["items"]:
            entity = entities[entity_id]
            caption = wrap(_caption(loc, entity_id), inner_w, CAPTION_SIZE)
            rows.append((entity, caption, _card_height(len(caption))))
        laid.append(rows)

    body_h = max(sum(h for _, _, h in rows) + 10 * (len(rows) - 1) for rows in laid)
    col_h = COL_HEAD_H + body_h + CARD_PAD

    for index, (column, rows) in enumerate(zip(fig.columns, laid)):
        x = MARGIN + index * (col_w + GUTTER)
        canvas.box(x, top, col_w, col_h, 10, f"col-{index}")
        canvas.text(x + col_w / 2, top + 22, _label(loc, f"col_{column['id']}"),
                    "col-head", anchor="middle")
        canvas.text(x + col_w / 2, top + 38,
                    _label(loc, f"col_{column['id']}_sub"), "col-sub", anchor="middle")

        y = top + COL_HEAD_H
        for entity, caption, height in rows:
            canvas.add(
                f'<g class="node" role="button" tabindex="0" '
                f'data-entity="{_esc(entity.id)}" '
                f'aria-label="{_esc(entity.name)}">'
                f"<title>{_esc(entity.name)}</title>"
            )
            canvas.box(x + 8, y, col_w - 16, height, 7, "card")
            canvas.text(x + 8 + CARD_PAD, y + CARD_PAD + TITLE_SIZE - 2,
                        entity.name, "card-title")
            canvas.lines(x + 8 + CARD_PAD, y + CARD_PAD + TITLE_SIZE + LINE_H,
                         caption, "card-cap")
            canvas.add("</g>")
            y += height + 10

        if index < count - 1:
            arrow_x = x + col_w + 1
            arrow_y = top + col_h / 2
            canvas.add(f'<path d="M{arrow_x:.1f} {arrow_y:.1f} h{GUTTER - 4:.1f}" '
                       f'class="flow" stroke="#2a5bd7" stroke-width="1.6" fill="none" '
                       f'marker-end="url(#{marker})"/>')

    return top + col_h


def _render_bands(canvas: _Canvas, fig: Figure, entities: dict[str, Entity],
                  loc: dict, top: float) -> float:
    width = fig.width - 2 * MARGIN
    y = top + 18

    for band in fig.bands:
        heading = _label(loc, f"band_{band['id']}")
        if "entity" in band:
            entity = entities[band["entity"]]
            caption = wrap(_caption(loc, entity.id), width - 40, CAPTION_SIZE)
            height = 30 + len(caption) * LINE_H + CARD_PAD
            canvas.add(
                f'<g class="node" role="button" tabindex="0" '
                f'data-entity="{_esc(entity.id)}" aria-label="{_esc(entity.name)}">'
                f"<title>{_esc(entity.name)}</title>"
            )
            canvas.box(MARGIN, y, width, height, 9, "band-lake")
            canvas.text(fig.width / 2, y + 21, heading, "band-head", anchor="middle")
            for index, line in enumerate(caption):
                canvas.text(fig.width / 2, y + 38 + index * LINE_H, line,
                            "band-cap", anchor="middle")
            canvas.add("</g>")
            y += height + 14
            continue

        items = band["items"]
        cols = len(items)
        cell_w = (width - 20) / cols
        wrapped = [wrap(_label(loc, key), cell_w - 14, CAPTION_SIZE) for key in items]
        height = 34 + max(len(w) for w in wrapped) * LINE_H + CARD_PAD
        canvas.box(MARGIN, y, width, height, 9, f"band-{band['id']}")
        canvas.text(fig.width / 2, y + 21, heading, "band-head", anchor="middle")
        for index, lines in enumerate(wrapped):
            cx = MARGIN + 10 + index * cell_w + cell_w / 2
            for line_index, line in enumerate(lines):
                canvas.text(cx, y + 40 + line_index * LINE_H, line, "band-item",
                            anchor="middle")
        y += height + 14

    return y


def _render_steps(canvas: _Canvas, fig: Figure, loc: dict, top: float,
                  marker: str = "arrow") -> float:
    width = min(430, fig.width - 2 * MARGIN)
    x = (fig.width - width) / 2
    y = top + 10
    step_h = 46
    for index, key in enumerate(fig.steps):
        canvas.box(x, y, width, step_h, 8, "step")
        canvas.text(fig.width / 2, y + 28, _label(loc, key), "step-label",
                    anchor="middle")
        if index < len(fig.steps) - 1:
            canvas.add(f'<path d="M{fig.width / 2:.1f} {y + step_h:.1f} v16" '
                       f'class="flow" stroke="#2a5bd7" stroke-width="1.6" fill="none" '
                       f'marker-end="url(#{marker})"/>')
        y += step_h + 22
    return y


FONT = "'Segoe UI',system-ui,-apple-system,'Helvetica Neue',sans-serif"

#: Light palette, emitted as presentation attributes.
#: librsvg does not resolve CSS custom properties -- a var()-based stylesheet
#: renders as a solid black rectangle. Presentation attributes always render,
#: and browser CSS still overrides them for dark mode.
SHAPE = {
    "col-0": ("#eef4ff", "#c8d3e8"), "col-1": ("#eefaf1", "#bcdcc6"),
    "col-2": ("#eef2ff", "#c6cdea"), "col-3": ("#f7effc", "#dcc8e8"),
    "card": ("#ffffff", "#ccd8ee"), "step": ("#ffffff", "#ccd8ee"),
    "band-lake": ("#e9f4fd", "#a9cdea"),
    "band-soc_operations": ("#fff8ec", "#e8d3ad"),
    "band-key_benefits": ("#f4f7fd", "#ccd8ee"),
    "bgfill": ("#ffffff", "none"),
}
TEXT = {
    "fig-title": ("#14203a", 21, 700), "fig-sub": ("#4a5876", 12.5, 400),
    "col-head": ("#2a5bd7", 15, 650), "col-sub": ("#4a5876", 10.5, 400),
    "card-title": ("#14203a", 13, 640), "card-cap": ("#4a5876", 10.5, 400),
    "band-head": ("#2a5bd7", 14, 650), "band-item": ("#4a5876", 10.5, 400),
    "band-cap": ("#4a5876", 10.5, 400), "step-label": ("#14203a", 13, 620),
}
DARK_SHAPE = {
    "col-0": ("#182338", "#334063"), "col-1": ("#152a22", "#2c4a39"),
    "col-2": ("#1a2038", "#334063"), "col-3": ("#241c34", "#453458"),
    "card": ("#1b2233", "#38456a"), "step": ("#1b2233", "#38456a"),
    "band-lake": ("#132635", "#2f5b7d"),
    "band-soc_operations": ("#2a2417", "#5c4c28"),
    "band-key_benefits": ("#161c2b", "#334063"),
    "bgfill": ("#11151f", "none"),
}
DARK_TEXT = {
    "fig-title": "#e9eefb", "fig-sub": "#a2b0cc", "col-head": "#8fb0ff",
    "col-sub": "#a2b0cc", "card-title": "#e9eefb", "card-cap": "#a2b0cc",
    "band-head": "#8fb0ff", "band-item": "#a2b0cc", "band-cap": "#a2b0cc",
    "step-label": "#e9eefb",
}


def _dark_css() -> str:
    rules = []
    for cls, (fill, stroke) in sorted(DARK_SHAPE.items()):
        decl = f"fill:{fill}" + (f";stroke:{stroke}" if stroke != "none" else "")
        rules.append(f".{cls}{{{decl}}}")
    for cls, fill in sorted(DARK_TEXT.items()):
        rules.append(f".{cls}{{fill:{fill}}}")
    rules.append(".flow{stroke:#8fb0ff}")
    rules.append(".arrowfill{fill:#8fb0ff}")
    body = "".join(rules)
    return (
        ".node{cursor:pointer}"
        ".node:hover .card,.node:focus .card{stroke:#2a5bd7;stroke-width:2}"
        f"@media (prefers-color-scheme:dark){{:root:not([data-theme=\"light\"]) {{}}{body}}}"
    )


def render_svg(fig: Figure, entities: dict[str, Entity], loc: dict) -> str:
    canvas = _Canvas()
    canvas.box(0, 0, fig.width, fig.height, 0, "bgfill")
    canvas.text(fig.width / 2, 34, _label(loc, f"fig_{fig.id}"), "fig-title",
                anchor="middle")
    canvas.text(fig.width / 2, 54, _label(loc, f"fig_{fig.id}_sub"), "fig-sub",
                anchor="middle")

    marker = f"arrow-{fig.id}-{loc.get('__locale', 'x')}"
    if fig.columns:
        bottom = _render_columns(canvas, fig, entities, loc, 74, marker)
        bottom = _render_bands(canvas, fig, entities, loc, bottom)
    else:
        bottom = _render_steps(canvas, fig, loc, 74, marker)

    # Fit the canvas to real content. The model's height is a hint for
    # authoring only; trailing whitespace would survive into PDF and PPTX.
    height = int(bottom + MARGIN)
    title = _label(loc, f"fig_{fig.id}")
    subtitle = _label(loc, f"fig_{fig.id}_sub")
    # Ids must be unique across the page: both languages inline all three
    # figures, and the lightbox clones one of them, so a shared "arrow" id put
    # seven identical ids in the document and every url(#arrow) resolved to the
    # first one in tree order.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fig.width} {height}" '
        f'width="{fig.width}" height="{height}" role="img" '
        f'aria-labelledby="{fig.id}-t {fig.id}-d">'
        f'<title id="{fig.id}-t">{_esc(title)}</title>'
        f'<desc id="{fig.id}-d">{_esc(subtitle)}</desc>'
        f"<style>{_dark_css()}</style>"
        f'<defs><marker id="{marker}" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M0 0 L10 5 L0 10 z" class="arrowfill" fill="#2a5bd7"/></marker></defs>'
        + "".join(canvas.parts)
        + "</svg>"
    )
