"""Header mapping (PRD F-D3 step 2): a deterministic synonym list (config/sheet_headers.yaml, team-owned).
A person confirms the proposal before anything is imported. (P1 #10: unknown headers may get a language-model
*suggestion*; a person still confirms.)"""

import re
from functools import lru_cache

import yaml

from app.settings import get_settings

FIELDS = ("name", "phone", "headcount", "location", "village", "district", "needs", "notes", "status", "time")


def _key(header: str) -> str:
    return re.sub(r"[\s\.\-_/?:()#]+", "", (header or "").strip().lower())


@lru_cache(maxsize=1)
def synonyms() -> tuple[dict[str, str], set[str]]:
    cfg = yaml.safe_load((get_settings().config_dir / "sheet_headers.yaml").read_text())
    table = {_key(w): f for f, words in cfg["fields"].items() for w in words}
    return table, {_key(w) for w in cfg.get("ignore", [])}


def propose(headers: list[str]) -> dict[str, str]:
    """header → field | 'ignore' | 'unknown'. Each field is used at most once (first column wins)."""
    table, ignore = synonyms()
    out, used = {}, set()
    for h in headers:
        k = _key(h)
        field = table.get(k)
        if field and field not in used:
            out[h] = field
            used.add(field)
        elif k in ignore or not k:
            out[h] = "ignore"
        else:
            out[h] = "unknown"
    return out


def validate(mapping: dict[str, str], headers: list[str]) -> list[str]:
    problems = []
    if set(mapping) != set(headers):
        problems.append("the mapping must cover exactly the sheet's headers")
    fields = [f for f in mapping.values() if f not in ("ignore", "unknown")]
    if any(f not in FIELDS for f in fields):
        problems.append(f"unknown field; use one of {list(FIELDS)} or 'ignore'")
    if len(fields) != len(set(fields)):
        problems.append("each field can come from one column only")
    if not ({"location", "village", "notes"} & set(fields)):
        problems.append("map at least one of location, village or notes, or rows can't be placed")
    return problems
