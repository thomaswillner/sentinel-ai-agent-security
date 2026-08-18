"""G7: every URL the brief cites must resolve."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ..http_evidence import fetch
from ..verdicts import EXIT_GATE_FAILURE, EXIT_OK


def classify_statuses(statuses: dict[str, int]) -> tuple[bool, list[tuple[str, int]]]:
    bad = sorted((url, code) for url, code in statuses.items() if code != 200)
    return (not bad), bad


def check(urls: list[str]) -> tuple[bool, list[tuple[str, int]]]:
    return classify_statuses({url: fetch(url).status for url in sorted(set(urls))})


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    recon = json.loads((root / "state" / "reconciliation.json").read_text(encoding="utf-8"))
    urls = [u for row in recon["entities"] for u in row["source_urls"].values()]
    urls.append(recon["article"]["source_url"])
    passed, bad = check(urls)
    for url, code in bad:
        print(f"DEAD {code} {url}", file=sys.stderr)
    print(f"link gate: {len(set(urls))} urls checked, {len(bad)} dead")
    return EXIT_OK if passed else EXIT_GATE_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
