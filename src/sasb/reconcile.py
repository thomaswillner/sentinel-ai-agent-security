"""Orchestrate the sweep and emit state/reconciliation.json.

This module owns the only clock read in the project. Generators receive the
timestamp through the reconciliation document, which is what keeps their output
byte-reproducible.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .article import ArticleRecord, load_article
from .i18n import LOCALES, check_completeness, load_locale
from .learn_probe import Probe, probe, verify_localized
from .model import Entity, load_entities
from .verdicts import EXIT_GATE_FAILURE, EXIT_INCONCLUSIVE, Verdict, exit_code_for

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "model" / "entities.yaml"
DEFAULT_OUT = ROOT / "state" / "reconciliation.json"
SCHEMA_VERSION = 1


def build_reconciliation(
    entities: list[Entity],
    probes: list[Probe],
    article: ArticleRecord,
    checked_at: str,
    localized: dict[str, dict[str, str]] | None = None,
) -> dict:
    """Pure. Same inputs always produce the same document."""
    by_id = {p.entity_id: p for p in probes}
    localized = localized or {}
    rows = []
    for entity in sorted(entities, key=lambda e: e.id):
        p = by_id[entity.id]
        sources = {"en": p.final_url}
        translated = {"en": True}
        for loc in LOCALES:
            if loc == "en":
                continue
            verified = localized.get(entity.learn_url, {}).get(loc)
            # The English URL is used when no translation verified, but the
            # substitution is recorded rather than silent: the page renders an
            # explicit notice and the link gate checks the URL actually shown.
            sources[loc] = verified or p.final_url
            translated[loc] = bool(verified)
        rows.append({
            "id": entity.id,
            "name": entity.name,
            "article_name": entity.article_name,
            "kind": entity.kind,
            "verdict": str(p.verdict),
            # Never substitute a default here: RENAMED carries status=None, and
# defaulting it to "ga" published an availability nobody measured.
            "status_detected": p.status_detected or "unknown",
            "final_url": p.final_url,
            "source_urls": dict(sorted(sources.items())),
            "source_translated": dict(sorted(translated.items())),
            "fingerprint": p.fingerprint,
            "evidence": list(p.evidence),
            "checked_at": checked_at,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "checked_at": checked_at,
        "article": {
            "message_id": article.message_id,
            "subject": article.subject,
            "author": article.author,
            "post_time": article.post_time,
            "last_edit_time": article.last_edit_time,
            "body_hash": article.body_hash,
            "labels": list(article.labels),
            "source_url": article.source_url,
        },
        "entities": rows,
        "summary": dict(sorted(Counter(r["verdict"] for r in rows).items())),
    }


def _verify_localized_urls(entities: list[Entity]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for url in sorted({e.learn_url for e in entities}):
        found: dict[str, str] = {}
        for loc in LOCALES:
            if loc == "en":
                continue
            verified = verify_localized(url, loc)
            if verified:
                found[loc] = verified
        out[url] = found
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reconcile the brief against Microsoft Learn.")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    entities = load_entities(args.model)
    # Run the translation-completeness gate in the sweep, not only under pytest.
    # A gate with no caller in the publish path is not a gate.
    try:
        check_completeness({name: load_locale(name) for name in LOCALES}, entities)
    except Exception as exc:
        print(f"FATAL: locale completeness gate failed: {exc}", file=sys.stderr)
        return EXIT_GATE_FAILURE
    if not entities:
        print("FATAL: empty watchlist", file=sys.stderr)
        return EXIT_GATE_FAILURE

    article = load_article()
    if article is None:
        print("FATAL: article source unreachable; refusing to report currency",
              file=sys.stderr)
        return EXIT_INCONCLUSIVE

    # A learn_url used by more than one entity is a shared reference page.
    shared = {u for u in (e.learn_url for e in entities)
              if sum(1 for e in entities if e.learn_url == u) > 1}
    probes = [probe(e, shared_page=e.learn_url in shared) for e in entities]
    localized = _verify_localized_urls(entities)
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_reconciliation(entities, probes, article, checked_at, localized)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for row in doc["entities"]:
        if row["verdict"] != Verdict.CURRENT:
            print(f"{row['verdict']:<12} {row['id']:<28} {'; '.join(row['evidence'])[:110]}")
    print(f"summary: {doc['summary']}")
    return exit_code_for([Verdict(r["verdict"]) for r in doc["entities"]])


if __name__ == "__main__":
    raise SystemExit(main())
