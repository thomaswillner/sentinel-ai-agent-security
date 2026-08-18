import json
from pathlib import Path

from sasb.article import parse_article

FIX = Path(__file__).parent / "fixtures"


def _payload() -> dict:
    return json.loads((FIX / "khoros_message.json").read_text())


def test_parses_known_payload():
    rec = parse_article(_payload())
    assert rec.message_id == "4542583"
    assert rec.subject == "Securing Enterprise AI Agents with Microsoft Sentinel"
    assert rec.author == "SantoshPargi"
    assert rec.post_time.startswith("2026-07-31")
    assert len(rec.body_hash) == 64
    assert "Agent 365" in rec.labels


def test_body_hash_is_stable():
    assert parse_article(_payload()).body_hash == parse_article(_payload()).body_hash
