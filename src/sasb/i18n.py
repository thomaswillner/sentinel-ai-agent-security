"""Locale loading with a completeness gate.

English is canonical: entity summaries live inline in model/entities.yaml.
German lives in model/i18n/de.yaml. UI strings and section narrative live in
model/i18n/<locale>.yaml under `ui:` and `sections:`.

The gate refuses a locale that is missing any key the canonical locale has, so
the page can never ship a half-translated row. This mirrors the publication
rule that an unknown state is never allowed.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .model import Entity, ModelError

DEFAULT_LOCALE = "en"
LOCALES = ("en", "de")
I18N_DIR = Path(__file__).resolve().parents[2] / "model" / "i18n"


def load_locale(locale: str, i18n_dir: Path | None = None) -> dict:
    path = (i18n_dir or I18N_DIR) / f"{locale}.yaml"
    if not path.exists():
        raise ModelError(f"missing locale file: {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # Tag the locale so generators can build locale-unique element ids without
    # each call site having to remember to pass the name separately.
    doc["__locale"] = locale
    return doc


def _leaf_keys(node: object, prefix: str = "") -> set[str]:
    if isinstance(node, dict):
        keys: set[str] = set()
        for k, v in node.items():
            keys |= _leaf_keys(v, f"{prefix}.{k}" if prefix else str(k))
        return keys
    return {prefix}


def check_completeness(locales: dict[str, dict], entities: list[Entity]) -> None:
    """Raise ModelError unless every locale covers every canonical key."""
    canonical = locales[DEFAULT_LOCALE]
    canon_keys = _leaf_keys({k: v for k, v in canonical.items()
                         if k not in ("entities", "__locale")})

    for name, doc in sorted(locales.items()):
        if name == DEFAULT_LOCALE:
            continue
        missing = sorted(
            canon_keys - _leaf_keys({k: v for k, v in doc.items()
                                     if k not in ("entities", "__locale")})
        )
        if missing:
            raise ModelError(f"locale {name!r} is missing keys: {missing[:10]}")

        translated = (doc.get("entities") or {})
        gaps = sorted(
            e.id for e in entities
            if not str((translated.get(e.id) or {}).get("summary", "")).strip()
        )
        if gaps:
            raise ModelError(f"locale {name!r} is missing entity summaries: {gaps[:10]}")


def summary_for(entity: Entity, locale: str, locales: dict[str, dict]) -> str:
    if locale == DEFAULT_LOCALE:
        return entity.summary
    return (locales[locale].get("entities") or {}).get(entity.id, {}).get(
        "summary", entity.summary
    )
