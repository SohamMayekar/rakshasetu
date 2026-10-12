"""Loads the team-owned YAML config (PRD §9) once per process, validated by Pydantic.

A bad file fails at boot with the exact key, not mid-demo. `reload_config()` exists for tests.
"""

import re
from datetime import timedelta
from functools import lru_cache
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.settings import get_settings

_DURATION = re.compile(r"^(\d+(?:\.\d+)?)(s|m|h)$")


def parse_duration(text: str | int | float) -> timedelta:
    """'30s' / '5m' / '2h' → timedelta. A bare number means seconds."""
    if isinstance(text, (int, float)):
        return timedelta(seconds=text)
    m = _DURATION.match(text.strip())
    if not m:
        raise ValueError(f"not a duration: {text!r} (use 30s, 5m or 2h)")
    n, unit = float(m.group(1)), m.group(2)
    return timedelta(seconds=n * {"s": 1, "m": 60, "h": 3600}[unit])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Weights(Strict):
    phone_or_device: float
    place: float
    geo: float
    landmarks: float
    headcount: float
    names: float
    time: float


class Dedupe(Strict):
    score: Literal["weighted_sum_missing_zero"]
    weights: Weights
    name_tokens: bool
    min_signals: int
    suggest_at: float
    auto_merge_at: float
    relay_phone_distinct_households: int
    block: dict[str, float]
    geo_min_confidence: Literal["high", "medium", "low"]
    reject_creates_block: bool
    transitive_merges: Literal[False]
    candidate_cap: int
    candidate_radius_km: float
    time_decay_hours: float
    include_closed_hours: float

    @model_validator(mode="after")
    def _weights_sum_to_one(self):
        total = sum(self.weights.model_dump().values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"dedupe weights must sum to 1.0 (they sum to {total:.2f})")
        return self


class Radius(Strict):
    two_landmarks: int
    one_landmark: int
    many_candidates_cap: int
    village: int
    district: int
    human: int


class LocationCfg(Strict):
    landmark_search_radius_m: int
    pair_max_gap_m: int
    high_requires_unique_pair_within_m: int
    radius_m: Radius
    village_fuzzy_min: int


class PriorityRule(Strict):
    level: Literal["P1", "P2", "P3", "P4"]
    when: str
    reason: str

    @field_validator("when")
    @classmethod
    def _readable(cls, v):
        from app.core.expr import parse
        parse(v)   # a typo or an unknown fact fails at boot, with the rule quoted
        return v


class Contact(Strict):
    acknowledge_within: dict[str, str]
    eta_chips: list[str]
    eta_grace: str
    onscene_window: str
    long_operation_window: str
    heartbeat_extends_deadline: Literal[False]
    team_level_contact: bool
    demo_clock_multiplier: int = Field(ge=1)
    rescue_review_window: str
    demo_rescue_review_window: str

    @field_validator("eta_grace", "onscene_window", "long_operation_window", "rescue_review_window",
                     "demo_rescue_review_window")
    @classmethod
    def _is_duration(cls, v):
        parse_duration(v)
        return v


class Config(Strict):
    profile: Literal["demo", "realistic"]
    dedupe: Dedupe
    location: LocationCfg
    priority: list[PriorityRule]
    p1_order: list[str]
    contact: Contact
    dispatch: dict
    escalation: dict
    rescue: dict
    demo: dict
    surge: dict
    scheduler: dict
    lanes: list[str]
    providers: dict
    llm: dict
    voice_caps: dict
    status_page: dict
    webhooks: dict = {}

    @model_validator(mode="after")
    def _last_rule_catches_all(self):
        if not self.priority or self.priority[-1].when.strip() != "true":
            raise ValueError("the last priority rule must be the catch-all `when: \"true\"`")
        return self


class Partner(Strict):
    id: str
    team: str
    domain: str
    secret_env: str
    scopes: list[str]
    subscriptions: list[str] = []
    incidents: list[str] = []
    rate_per_min: int = 60
    enabled: bool = True
    lane: str | None = None      # job lane for this partner's reports; default whatsapp_partner (surge: synthetic load)
    webhook_url_env: str | None = None   # env var holding the partner's webhook URL; unset or empty = nothing is sent


class Roles(Strict):
    roles: dict[str, dict]
    permissions: dict[str, list[str]]

    @model_validator(mode="after")
    def _known_roles_only(self):
        for action, roles in self.permissions.items():
            unknown = set(roles) - set(self.roles)
            if unknown:
                raise ValueError(f"permission {action} names unknown roles {sorted(unknown)}")
        return self

    def allows(self, role: str, action: str) -> bool:
        return role in self.permissions.get(action, [])


class Bundle(Strict):
    config: Config
    roles: Roles
    flags: dict[str, bool]
    partners: list[Partner]


def _load(name: str):
    return yaml.safe_load((get_settings().config_dir / name).read_text())


@lru_cache(maxsize=1)
def get_bundle() -> Bundle:
    return Bundle(config=_load("rakshasetu.config.yaml"), roles=_load("roles.yaml"),
                  flags=_load("flags.yaml"), partners=_load("partners.yaml")["partners"])


def get_config() -> Config:
    return get_bundle().config


def reload_config() -> Bundle:
    get_bundle.cache_clear()
    return get_bundle()
