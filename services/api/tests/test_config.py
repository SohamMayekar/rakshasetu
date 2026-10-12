from datetime import timedelta

import pytest
import yaml
from pydantic import ValidationError

from app.config import Config, get_bundle, parse_duration
from app.settings import get_settings


def test_the_committed_config_loads():
    b = get_bundle()
    assert b.config.dedupe.weights.phone_or_device == 0.30
    assert b.config.contact.demo_clock_multiplier == 60
    assert b.roles.allows("duty_officer", "assignment.create")
    assert not b.roles.allows("call_taker", "assignment.create")
    assert not b.roles.allows("team_lead", "case.check")
    assert b.flags["family_check"] is True
    assert b.partners[0].id == "demo-partner"


@pytest.mark.parametrize("text,expected", [("30s", 30), ("5m", 300), ("2h", 7200), (45, 45)])
def test_durations(text, expected):
    assert parse_duration(text) == timedelta(seconds=expected)


def test_bad_duration_is_refused():
    with pytest.raises(ValueError):
        parse_duration("five minutes")


def _raw():
    return yaml.safe_load((get_settings().config_dir / "rakshasetu.config.yaml").read_text())


def test_weights_must_sum_to_one():
    raw = _raw()
    raw["dedupe"]["weights"]["phone_or_device"] = 0.9
    with pytest.raises(ValidationError, match="sum to 1.0"):
        Config.model_validate(raw)


def test_heartbeat_can_never_extend_a_deadline():
    raw = _raw()
    raw["contact"]["heartbeat_extends_deadline"] = True
    with pytest.raises(ValidationError):
        Config.model_validate(raw)


def test_chains_of_merges_are_not_configurable():
    raw = _raw()
    raw["dedupe"]["transitive_merges"] = True
    with pytest.raises(ValidationError):
        Config.model_validate(raw)


def test_priority_rules_need_a_catch_all():
    raw = _raw()
    raw["priority"] = raw["priority"][:-1]
    with pytest.raises(ValidationError, match="catch-all"):
        Config.model_validate(raw)


def test_unknown_keys_are_refused():
    raw = _raw()
    raw["dedupe"]["wieghts_typo"] = 1
    with pytest.raises(ValidationError):
        Config.model_validate(raw)
