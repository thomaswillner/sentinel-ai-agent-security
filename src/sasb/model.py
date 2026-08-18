"""Canonical model loading with strict schema validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import yaml

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "model" / "schema"


class ModelError(Exception):
    """Raised when the canonical model violates its contract."""


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    kind: str
    learn_url: str
    expected_status: str
    summary: str
    article_name: str | None = None
    anchor: str | None = None


def _validate(doc: object, schema_name: str) -> None:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        detail = first.message
        if "Additional properties" in detail or "additionalProperties" in detail:
            detail = f"unknown key -- {detail}"
        raise ModelError(f"{schema_name}: {detail} at {list(first.path)}")


def load_entities(path: Path) -> list[Entity]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    _validate(doc, "entities.schema.json")
    entities = [Entity(**item) for item in doc["entities"]]
    seen: set[str] = set()
    for e in entities:
        if e.id in seen:
            raise ModelError(f"duplicate entity id: {e.id}")
        seen.add(e.id)
    return sorted(entities, key=lambda e: e.id)
