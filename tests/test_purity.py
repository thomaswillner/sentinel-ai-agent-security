"""Generators must never touch the network or the clock.

The reconciliation sweep owns the only clock read and the only network calls.
If a generator acquired either, builds would stop being reproducible and G5
would start failing intermittently instead of loudly.
"""
from pathlib import Path

import pytest

BUILD = Path("src/sasb/build")
FORBIDDEN = ("urllib", "requests", "socket", "datetime.now", "time.time",
             "date.today", "random.")


@pytest.mark.parametrize("module", sorted(BUILD.glob("*.py")), ids=lambda p: p.name)
def test_generator_is_pure(module):
    source = module.read_text(encoding="utf-8")
    hits = [token for token in FORBIDDEN if token in source]
    assert not hits, f"{module.name} must not use {hits}; builds must be reproducible"
