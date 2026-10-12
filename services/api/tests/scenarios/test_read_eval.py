"""How well the word rules read real-looking reports (m86): labelled messages in data/eval/reports.yaml.

Two sets: `reports` (40, the lists were improved against them) and `holdout` (20, written afterwards and never
tuned on; its score is the honest one).

The place is scored the way the pipeline finds it: the known place the words point to (fuzzy, any script), else a
known place named anywhere in the text (the gazetteer scan, stage 1d), else the words' own place name for a
village the map doesn't know. Everything else is the word rules alone.

Prints one line per field (found right · wrong · missed) and every miss, then holds the scores at or above
the floors below, so a dictionary change can't quietly make reading worse. `make read-eval` runs it with -s.
"""

from collections import Counter

import pytest
import yaml

from app.modules.location.ladder import match_place
from app.modules.location.names import norm
from app.pipeline.keywords import extract_keywords
from app.settings import get_settings
from tests.conftest import needs_db, one

SETS = ("hazards", "needs", "vulnerable", "landmarks")
ONES = ("people", "village", "phone", "on_site")
FLOOR = {"reports": 0.97, "holdout": 0.85}   # share of labelled facts found, and of facts read that are right


def _read(x, place) -> dict:
    v = x.location.village_or_locality
    return {
        "people": x.people_count.value if x.people_count else None,
        "village": norm(place.name) if place else norm(v.latin) if v else None,
        "phone": x.callback_phone[-10:] if x.callback_phone else None,
        "on_site": x.reporter_on_site,
        "hazards": {h.type for h in x.hazards}, "needs": {n.type for n in x.needs},
        "vulnerable": {v.type for v in x.vulnerable}, "landmarks": {lm.type for lm in x.location.landmarks},
    }


@needs_db
@pytest.mark.parametrize("which", ["reports", "holdout"])
def test_read_eval(seeded, app_db, which):
    incident = one(app_db, "SELECT id FROM incidents WHERE code = 'BR'")
    reports = yaml.safe_load((get_settings().data_dir / "eval" / "reports.yaml").read_text())[which]
    score: dict[str, Counter] = {f: Counter() for f in SETS + ONES}
    misses = []
    for r in reports:
        ex = extract_keywords(r["text"])
        with app_db.connect() as conn:
            place = match_place(conn, incident, ex, r["text"])[0]
        got = _read(ex, place)
        for f in SETS:
            want = set(r.get(f, []))
            score[f].update(right=len(want & got[f]), wrong=len(got[f] - want), missed=len(want - got[f]))
            if want != got[f]:
                misses.append(f"{f:<10} want {sorted(want)} got {sorted(got[f])} · {r['text'][:70]}")
        for f in ONES:
            want = r.get(f)
            if f == "village" and want:
                want = norm(want)
            g = got[f]
            if want is None and g is None:
                continue
            key = "right" if g == want else "missed" if g is None else "wrong"
            score[f][key] += 1
            if key != "right":
                misses.append(f"{f:<10} want {want!r} got {g!r} · {r['text'][:70]}")

    print(f"\n{which}: {len(reports)} messages · field: right / wrong / missed")
    for f, c in score.items():
        print(f"  {f:<10} {c['right']:>3} / {c['wrong']:>2} / {c['missed']:>2}")
    print("\n".join(["misses:"] + misses) if misses else "no misses")

    total = sum(score.values(), Counter())
    found = total["right"] / (total["right"] + total["missed"])
    precise = total["right"] / (total["right"] + total["wrong"])
    print(f"found {found:.0%} of labelled facts; {precise:.0%} of what was read is right")
    assert found >= FLOOR[which] and precise >= FLOOR[which]
