"""Pydantic mirrors of packages/contracts/*.schema.json (contracts first).

`tests/test_contracts.py` checks these models and the JSON schemas agree on valid and invalid documents.
The extraction model is the closed schema the language model must fit (rule R13): no priority, no summary.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Channel = Literal["voice", "whatsapp", "web_form", "spreadsheet", "partner"]
Relation = Literal["self", "family", "neighbour", "volunteer", "forwarder", "official", "unknown"]
Hazard = Literal["trapped_on_roof", "trapped_inside", "water_entering", "water_rising", "strong_current",
                 "buried", "structure_collapsed", "landslide", "cut_off"]
Need = Literal["rescue", "medicine", "medical_urgent", "food", "drinking_water", "shelter", "baby_supplies"]
Vulnerable = Literal["elderly", "infant", "child", "pregnant", "disabled", "sick", "injured"]
LandmarkType = Literal["temple", "mosque", "church", "gurdwara", "place_of_worship", "bridge", "school", "hospital",
                       "water_tower", "railway_station", "police_station", "market", "panchayat_bhawan", "canal", "tower"]
LandmarkRelation = Literal["behind", "near", "opposite", "beside", "in_front", "inside", "unknown"]

Quote = Field(min_length=1, max_length=300)


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Canonical Report v1 (PRD §11.2) -------------------------------------------------------------

class Reporter(Closed):
    phone: str | None = Field(default=None, max_length=40)
    device_id: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=200)
    relation: Relation = "unknown"


class Content(Closed):
    text: str | None = Field(default=None, max_length=20000)
    language: str | None = Field(default=None, max_length=10)
    audio_ref: str | None = None
    attachments: list[str] = Field(default_factory=list, max_length=10)


class Source(Closed):
    system: str | None = None
    ref: str | None = None
    file_sha256: str | None = None
    row: int | None = None
    partner: str | None = None
    simulated: bool = False
    written_at: datetime | None = None
    synced_at: datetime | None = None


class CanonicalReport(Closed):
    schema_version: Literal["1"]
    idempotency_key: str = Field(min_length=1, max_length=200)
    channel: Channel
    incident_hint: str | None = Field(default=None, pattern=r"^[A-Z]{2,4}$")
    received_at: datetime | None = None
    reporter: Reporter = Field(default_factory=Reporter)
    content: Content
    structured: dict | None = None
    source: Source = Field(default_factory=Source)


# --- Extraction v1 (PRD §8.2) ---------------------------------------------------------------------

class PeopleCount(Closed):
    value: int = Field(ge=0, le=5000)
    kind: Literal["stated", "estimated"]
    quote: str = Quote


class HazardItem(Closed):
    type: Hazard
    quote: str = Quote


class NeedItem(Closed):
    type: Need
    quote: str = Quote


class VulnerableItem(Closed):
    type: Vulnerable
    quote: str = Quote


class Village(Closed):
    original: str = Field(max_length=100)
    latin: str = Field(max_length=100)
    quote: str = Quote


class Landmark(Closed):
    type: LandmarkType
    name: str | None = Field(max_length=100)
    relation: LandmarkRelation
    quote: str = Quote


class Location(Closed):
    village_or_locality: Village | None
    district: str | None = Field(max_length=100)
    state: str | None = Field(max_length=100)
    landmarks: list[Landmark] = Field(max_length=6)


class PersonName(Closed):
    name: str = Field(max_length=100)
    quote: str = Quote


class Extraction(Closed):
    """Every key is required, as in the JSON schema: the model must say "none" explicitly."""
    language: str | None = Field(max_length=10)
    people_count: PeopleCount | None
    hazards: list[HazardItem] = Field(max_length=10)
    needs: list[NeedItem] = Field(max_length=10)
    vulnerable: list[VulnerableItem] = Field(max_length=10)
    location: Location
    person_names: list[PersonName] = Field(max_length=10)
    callback_phone: str | None = Field(max_length=40)
    reporter_on_site: bool | None

    @classmethod
    def empty(cls, language: str | None = None) -> "Extraction":
        return cls(language=language, people_count=None, hazards=[], needs=[], vulnerable=[],
                   location=Location(village_or_locality=None, district=None, state=None, landmarks=[]),
                   person_names=[], callback_phone=None, reporter_on_site=None)
