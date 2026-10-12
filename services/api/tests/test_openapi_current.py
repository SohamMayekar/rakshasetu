"""The committed OpenAPI document must match the running code (contracts first). Fix: `make contracts`."""

import json

from app.main import create_app
from app.settings import get_settings


def test_committed_openapi_matches_the_code():
    committed = json.loads((get_settings().contracts_dir / "openapi.json").read_text())
    assert committed == json.loads(json.dumps(create_app().openapi())), "run `make contracts` and commit the result"
