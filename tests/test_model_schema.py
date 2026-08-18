from pathlib import Path

import pytest

from sasb.model import ModelError, load_entities

FIX = Path(__file__).parent / "fixtures"


def test_real_model_loads_and_is_nonempty():
    ents = load_entities(Path("model/entities.yaml"))
    assert len(ents) >= 20
    assert all(e.learn_url.startswith("https://learn.microsoft.com/") for e in ents)


def test_unknown_key_is_rejected():
    with pytest.raises(ModelError, match="unknown"):
        load_entities(FIX / "bad_entities_unknown_key.yaml")


def test_duplicate_id_is_rejected():
    with pytest.raises(ModelError, match="duplicate"):
        load_entities(FIX / "bad_entities_dup_id.yaml")
