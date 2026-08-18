"""Render generated SVG figures to PNG at several scales.

Inline SVG is not reliably right-click-saveable in browsers, so every figure is
also published as real PNG files that a download link can point at.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..gates.visual import _require

DEFAULT_SCALES = (1, 2, 4)


def render_pngs(svg_path: Path, out_dir: Path, stem: str,
                scales: tuple[int, ...] = DEFAULT_SCALES) -> list[Path]:
    rsvg = _require("rsvg-convert")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for scale in scales:
        target = out_dir / f"{stem}@{scale}x.png"
        subprocess.run([rsvg, "-z", str(scale), "-o", str(target), str(svg_path)],
                       check=True, capture_output=True)
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    dist = Path(__file__).resolve().parents[3] / "dist"
    count = 0
    for svg in sorted(dist.glob("*.svg")):
        render_pngs(svg, dist, svg.stem)
        count += 1
    print(f"rasterised {count} figures at {DEFAULT_SCALES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
