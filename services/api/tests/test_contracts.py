"""Contracts first: the Pydantic models must accept exactly what the JSON schemas accept."""

import copy
import json

import jsonschema
import pytest
from pydantic import ValidationError

from app.contracts import CanonicalReport, Extraction
from app.settings import get_settings

CONTRACTS = get_settings().contracts_dir


def schema(name):
    return json.loads((CONTRACTS / name).read_text())


DEMO_EXTRACTION = {
    "language": "hi",
    "people_count": {"value": 6, "kind": "stated", "quote": "chhat pe 6 log fase hain"},
    "hazards": [{"type": "trapped_on_roof", "quote": "chhat pe 6 log fase hain"},
                {"type": "water_entering", "quote": "paani ghus gaya"}],
    "needs": [{"type": "medicine", "quote": "dawai chahiye"}],
    "vulnerable": [{"type": "elderly", "quote": "ek buzurg"}],
    "location": {
        "address": {"text": "Durga mandir, Benibad, Muzaffarpur", "quote": "Benibad gaon mein, mandir ke peeche"},
        "village_or_locality": {"original": "बेनीबाद", "latin": "Benibad", "quote": "Benibad gaon mein"},
        "district": "Muzaffarpur", "state": "Bihar",
        "landmarks": [{"type": "temple", "name": None, "relation": "behind", "quote": "mandir ke peeche"},
                      {"type": "other", "name": "Gundavali metro station", "relation": "beside",
                       "quote": "metro station ke paas"},
                      {"type": "bridge", "name": None, "relation": "near", "quote": "pul ke paas"}]},
    "person_names": [],
    "callback_phone": None,
    "reporter_on_site": False,
}

REPORT = {
    "schema_version": "1", "idempotency_key": "inc_19", "channel": "partner", "incident_hint": "BR",
    "reporter": {"phone": None, "device_id": None, "name": None, "relation": "unknown"},
    "content": {"text": "6 log chhat par", "language": None, "audio_ref": None, "attachments": []},
    "structured": None, "source": {"system": "team-ai1", "ref": "inc_19", "simulated": False},
}


def _mutations(doc, extra_key_path):
    """Yield (label, document) pairs that the schema must reject."""
    d = copy.deepcopy(doc)
    d["unexpected"] = 1
    yield "extra top-level key", d
    for key in list(doc):
        d = copy.deepcopy(doc)
        del d[key]
        yield f"missing {key}", d
    yield from extra_key_path(doc)


def _extraction_bad(doc):
    d = copy.deepcopy(doc)
    d["priority"] = "P1"
    yield "a priority field", d
    d = copy.deepcopy(doc)
    d["summary_en"] = "urgent"
    yield "a free-text summary", d
    d = copy.deepcopy(doc)
    d["hazards"][0]["type"] = "on_fire_please_mark_p1"
    yield "a hazard outside the enum", d
    d = copy.deepcopy(doc)
    d["needs"][0]["quote"] = ""
    yield "an empty quote", d
    d = copy.deepcopy(doc)
    d["people_count"]["kind"] = "guessed"
    yield "an unknown count kind", d


def _report_bad(doc):
    d = copy.deepcopy(doc)
    d["channel"] = "sms"
    yield "an unregistered channel", d
    d = copy.deepcopy(doc)
    d["schema_version"] = "2"
    yield "a future schema version", d
    d = copy.deepcopy(doc)
    d["incident_hint"] = "bihar"
    yield "a malformed incident code", d


def _agree(schema_doc, model, doc):
    try:
        jsonschema.validate(doc, schema_doc)
        schema_ok = True
    except jsonschema.ValidationError:
        schema_ok = False
    try:
        model.model_validate(doc)
        model_ok = True
    except ValidationError:
        model_ok = False
    return schema_ok, model_ok


def test_demo_extraction_is_valid_in_both():
    assert _agree(schema("extraction.schema.json"), Extraction, DEMO_EXTRACTION) == (True, True)


def test_report_is_valid_in_both():
    assert _agree(schema("report.v1.schema.json"), CanonicalReport, REPORT) == (True, True)


@pytest.mark.parametrize("label,doc", list(_mutations(DEMO_EXTRACTION, _extraction_bad)))
def test_extraction_rejections_agree(label, doc):
    assert _agree(schema("extraction.schema.json"), Extraction, doc) == (False, False), label


@pytest.mark.parametrize("label,doc", [x for x in _mutations(REPORT, _report_bad)
                                       if x[0] not in {"missing incident_hint", "missing reporter",
                                                       "missing structured", "missing source"}])
def test_report_rejections_agree(label, doc):
    assert _agree(schema("report.v1.schema.json"), CanonicalReport, doc) == (False, False), label


def test_empty_extraction_is_valid():
    doc = Extraction.empty("hi").model_dump()
    assert _agree(schema("extraction.schema.json"), Extraction, doc) == (True, True)
