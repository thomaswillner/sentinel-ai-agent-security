"""Verdict taxonomy and exit-code policy.

Exit codes: 0 success | 2 drift needs review | 3 inconclusive | 4 gate failure.

Two rules govern this module:

1. NOT_FOUND is never publishable. A watched entity that cannot be located is a
   hard gate failure, so the page can only ever contain entities in a known,
   explained state. There is no "unknown" row on the published brief.
2. A recorded failure outranks an inconclusive one. NOT_FOUND is checked before
   UNREACHABLE, otherwise an unreachable source later in the list would launder
   a definite failure into a softer exit code.
"""
from __future__ import annotations

from enum import StrEnum

EXIT_OK = 0
EXIT_DRIFT = 2
EXIT_INCONCLUSIVE = 3
EXIT_GATE_FAILURE = 4


class Verdict(StrEnum):
    CURRENT = "CURRENT"
    CHANGED = "CHANGED"
    RENAMED = "RENAMED"
    DEPRECATED = "DEPRECATED"
    NOT_FOUND = "NOT_FOUND"
    UNREACHABLE = "UNREACHABLE"


#: Verdicts that may appear on the published page. Each is a known, explained state.
PUBLISHABLE = frozenset(
    {Verdict.CURRENT, Verdict.CHANGED, Verdict.RENAMED, Verdict.DEPRECATED}
)
#: Reviewable drift -- publishable, but flagged.
DRIFT_VERDICTS = frozenset({Verdict.CHANGED, Verdict.RENAMED, Verdict.DEPRECATED})
#: Definite failures. Never publishable.
BLOCKING_VERDICTS = frozenset({Verdict.NOT_FOUND})


def exit_code_for(verdicts: list[Verdict]) -> int:
    if any(v in BLOCKING_VERDICTS for v in verdicts):
        return EXIT_GATE_FAILURE
    if Verdict.UNREACHABLE in verdicts:
        return EXIT_INCONCLUSIVE
    if any(v in DRIFT_VERDICTS for v in verdicts):
        return EXIT_DRIFT
    return EXIT_OK


def assert_publishable(verdicts: list[Verdict]) -> None:
    """Raise unless every verdict is a known, explained, publishable state."""
    bad = sorted({str(v) for v in verdicts if v not in PUBLISHABLE})
    if bad:
        raise ValueError(
            f"refusing to publish: {bad} is not a known state; "
            "re-pin the entity in model/entities.yaml"
        )
