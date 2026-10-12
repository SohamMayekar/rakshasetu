"""Turn a validated Extraction into case fields, with provenance per field (PRD F-C13).

Each value remembers: how it was obtained (ai · rule · human · partner), the exact quote, which report,
and whether a person has checked it. The row's one-line summary is a TEMPLATE over validated fields,
never text written by a model ("6 people · roof · water inside · medicine · elderly").
"""

from app.contracts import Extraction

HAZARD_LABEL = {"trapped_on_roof": "roof", "trapped_inside": "trapped", "water_entering": "water inside",
                "water_rising": "water rising", "strong_current": "strong current", "buried": "buried",
                "structure_collapsed": "collapse", "landslide": "landslide", "cut_off": "cut off"}
NEED_LABEL = {"rescue": "rescue", "medicine": "medicine", "medical_urgent": "urgent medical", "food": "food",
              "drinking_water": "drinking water", "baby_supplies": "baby milk"}

METHOD_OF = {"ai": "ai", "rules": "rule", "structured": "partner"}


def summary(people: int | None, kind: str | None, hazards: list[str], needs: list[str], vulnerable: list[str]) -> str:
    parts = []
    if people:
        parts.append(f"{'~' if kind == 'estimated' else ''}{people} {'person' if people == 1 else 'people'}")
    parts += [HAZARD_LABEL.get(h, h) for h in hazards[:2]]
    parts += [NEED_LABEL.get(n, n) for n in needs[:2]]
    parts += vulnerable[:2]
    return " · ".join(parts) or "no details yet: listen or call back"


def fields_from_extraction(ex: Extraction, method: str, report_id: int) -> dict:
    m = METHOD_OF[method]

    def prov(value, quote):
        return {"value": value, "method": m, "quote": quote, "report_id": report_id, "checked": False}

    hazards = [h.type for h in ex.hazards]
    needs = [n.type for n in ex.needs]
    vulnerable = [v.type for v in ex.vulnerable]
    provenance = {
        "hazards": [prov(h.type, h.quote) for h in ex.hazards],
        "needs": [prov(n.type, n.quote) for n in ex.needs],
        "vulnerable": [prov(v.type, v.quote) for v in ex.vulnerable],
        "landmarks": [prov({"type": lm.type, "name": lm.name, "relation": lm.relation}, lm.quote)
                      for lm in ex.location.landmarks],
    }
    if ex.people_count:
        provenance["people_count"] = prov(ex.people_count.value, ex.people_count.quote)
    village = ex.location.village_or_locality
    if village:
        provenance["place"] = prov(village.latin, village.quote)
    for p in ex.person_names:
        provenance.setdefault("names", []).append(prov(p.name, p.quote))
    return {
        "people_count": ex.people_count.value if ex.people_count else None,
        "people_count_kind": ex.people_count.kind if ex.people_count else None,
        "hazards": hazards, "needs": needs, "vulnerable": vulnerable,
        "location_text": village.latin if village else None,
        "provenance": provenance,
        "summary": summary(ex.people_count.value if ex.people_count else None,
                           ex.people_count.kind if ex.people_count else None, hazards, needs, vulnerable),
        "attributes": {"person_names": [p.name for p in ex.person_names],
                       "reporter_on_site": ex.reporter_on_site},
    }
