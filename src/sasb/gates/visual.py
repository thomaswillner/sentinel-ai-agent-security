"""G4: prove the generated diagram is legible, not merely well-formed.

A structurally valid SVG can still render text off-canvas, too small, or
overlapped. This gate rasterises the real file and reads it back with OCR, so a
figure has to survive rendering before it can be published.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class ToolMissing(RuntimeError):
    """A required external renderer is unavailable -- inconclusive, not a pass."""


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise ToolMissing(f"{tool} not found; cannot verify rendering")
    return path


def render_png(svg_path: Path, png_path: Path, scale: int = 4) -> Path:
    rsvg = _require("rsvg-convert")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([rsvg, "-z", str(scale), "-o", str(png_path), str(svg_path)],
                   check=True, capture_output=True)
    return png_path


def ocr_text(png_path: Path) -> str:
    tess = _require("tesseract")
    out = subprocess.run([tess, str(png_path), "stdout"],
                         check=True, capture_output=True, text=True).stdout
    return " ".join(out.split())


def check(svg_path: Path, expect_tokens: list[str], *, scale: int = 4
          ) -> tuple[bool, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        png = render_png(svg_path, Path(tmp) / "render.png", scale)
        text = ocr_text(png).lower()
    missing = [t for t in expect_tokens if t.lower() not in text]
    return (not missing), missing
