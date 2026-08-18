from sasb.gates.links import classify_statuses


def test_all_ok_passes():
    passed, bad = classify_statuses({"https://a": 200, "https://b": 200})
    assert passed and bad == []


def test_dead_link_fails_the_gate():
    passed, bad = classify_statuses({"https://a": 200, "https://dead": 404})
    assert not passed
    assert ("https://dead", 404) in bad


def test_unreachable_also_fails_the_gate():
    passed, _ = classify_statuses({"https://x": 0})
    assert not passed
