"""Print the brief to PDF with headless Chromium.

The page carries print styles, so a reader can always use the browser's own
print dialog. This produces a deterministic build artifact as well, one per
locale, so the download link points at a real file rather than an instruction.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..gates.visual import ToolMissing
from ..i18n import LOCALES

CANDIDATES = (
    "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)
MIN_BYTES = 1024


def find_chrome() -> str:
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    for candidate in CANDIDATES:
        found = shutil.which(candidate) if "/" not in candidate else (
            candidate if Path(candidate).exists() else None)
        if found:
            return found
    raise ToolMissing("no Chromium/Chrome binary found; cannot render PDF")


def render(html_path: Path, out: Path, locale: str = "en") -> Path:
    chrome = find_chrome()
    out.parent.mkdir(parents=True, exist_ok=True)
    url = f"file://{html_path.resolve()}?lang={locale}"
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-sandbox",
         "--no-pdf-header-footer", "--virtual-time-budget=8000",
         f"--print-to-pdf={out}", url],
        check=True, capture_output=True, timeout=180,
    )
    if not out.exists() or out.stat().st_size < MIN_BYTES:
        raise RuntimeError(f"PDF render produced no usable output: {out}")
    return out


def main(argv: list[str] | None = None) -> int:
    dist = Path(__file__).resolve().parents[3] / "dist"
    index = dist / "index.html"
    for locale in LOCALES:
        target = render(index, dist / f"brief.{locale}.pdf", locale)
        print(f"  {target.name}  {target.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
