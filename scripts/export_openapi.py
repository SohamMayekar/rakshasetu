"""Write the API's OpenAPI document to packages/contracts/openapi.json (run `make contracts`)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.main import create_app


def openapi_text() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    out = ROOT / "packages" / "contracts" / "openapi.json"
    out.write_text(openapi_text())
    print(f"wrote {out.relative_to(ROOT)}")
