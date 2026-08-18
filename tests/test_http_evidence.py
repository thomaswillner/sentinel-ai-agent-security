import pytest

from sasb.verdicts import Verdict, assert_publishable, exit_code_for


def test_all_current_is_success():
    assert exit_code_for([Verdict.CURRENT, Verdict.CURRENT]) == 0


def test_drift_is_exit_two():
    assert exit_code_for([Verdict.CURRENT, Verdict.DEPRECATED]) == 2


def test_unreachable_outranks_drift_and_is_exit_three():
    # Inconclusive must never be laundered into a pass or a mere review flag.
    assert exit_code_for([Verdict.CURRENT, Verdict.DEPRECATED, Verdict.UNREACHABLE]) == 3


def test_unreachable_alone_is_never_success():
    assert exit_code_for([Verdict.UNREACHABLE]) != 0


def test_not_found_is_a_hard_gate_failure():
    # "not found" is never allowed on the published page.
    assert exit_code_for([Verdict.CURRENT, Verdict.NOT_FOUND]) == 4


def test_recorded_failure_outranks_inconclusive():
    # A trailing UNREACHABLE must not launder a definite NOT_FOUND into exit 3.
    assert exit_code_for([Verdict.NOT_FOUND, Verdict.UNREACHABLE]) == 4


def test_publishable_guard_accepts_known_states():
    assert_publishable([Verdict.CURRENT, Verdict.RENAMED, Verdict.DEPRECATED])


@pytest.mark.parametrize("bad", [Verdict.NOT_FOUND, Verdict.UNREACHABLE])
def test_publishable_guard_rejects_unknown_states(bad):
    with pytest.raises(ValueError, match="not a known state"):
        assert_publishable([Verdict.CURRENT, bad])
