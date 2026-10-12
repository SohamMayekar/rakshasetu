"""Generate a pack's 300-row demo volunteer sheet and its ground truth (PRD F-D3, §16.1 scene 1:15).

    python scripts/gen_demo_sheet.py              (from the repo root, with services/api/.venv): BR
    python scripts/gen_demo_sheet.py --pack MH    Mumbai

Writes data/scenarios/<pack>/sheet/volunteer_sheet.csv (as a volunteer's Excel saved it: mixed phone formats,
misspelt villages, blank cells, 14 phones already damaged by Excel) and ground_truth.csv (which household each
row really is, and what the import should do with it). The screens are English-only for now (decision D17), so
the sheet is in English; the importer still reads Hindi and Hinglish headers and cells. Every English list has
the same length as the Hinglish one it replaced, so the random stream (and every household) is unchanged.

Deterministic (fixed seed). People and phone numbers are synthetic and never dialled; places are real OSM
features from the committed gazetteer. The live demo's own place is left out on purpose (Thawe; Kurla West).
Every misspelling is checked against the same fuzzy rule the location ladder uses, so the rows the generator
calls "rules can read" really are; the rows it calls "needs AI" have no headcount the rules can find.
"""

import argparse
import csv
import io
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.modules.location.names import norm
from rapidfuzz import fuzz

ROWS = 300
FUZZY_MIN = 85          # rakshasetu.config.yaml location.village_fuzzy_min

# Villages whose words name ONE mapped landmark of that type within 2 km (checked against the gazetteer in
# m31), so a row that says it gets a Medium pin on that landmark, and two rows about one household overlap.
LANDMARKED = {
    "Kalu Chhapra": ["near the school", "behind the school", "next to the school"],
    "Bhore": ["near the hospital", "opposite the hospital"],
    "Hathua": ["opposite the hospital", "near the hospital"],
    "Katiya": ["behind the hospital", "near the hospital"],
    "Phulwaria": ["near the hospital", "beside the hospital"],
    "Kuchaikote": ["near the station", "opposite the railway station"],
    "Barauli": ["near the station", "behind the station"],
    "Mirganj": ["near the railway station", "opposite the station"],
    "Sidhwalia": ["near the station", "next to the station"],
    "Babutola": ["near the station"],
    "Manjha": ["near the station", "beside the station"],
    "Panchdeuri": ["near the station"],
    "Meera Chhapra": ["near the school", "opposite the school"],
    "Nirkhi Chhapra": ["near the school"],
    "Barasra": ["near the school"],
}
VILLAGE_ONLY = ["Uchkagaon", "Dewapur", "Nawadah", "Baikunthpur", "Bijaipur", "Nautan", "Lakri Nabiganj",
                "Taiya Dumri", "Panditpur", "Ansari Dumri", "Harpur", "Khanpur"]
VARIANTS = {   # how volunteers actually spell them; each is checked to still match by the ≥ 85 fuzzy rule
    "Hathua": ["Hathuwa", "Hatua"], "Kuchaikote": ["Kuchaikot", "Kuchaykote"], "Mirganj": ["Meerganj", "Mirgunj"],
    "Barauli": ["Barouli", "Baraulee"], "Sidhwalia": ["Sidhwaliya", "Sidhwalya"], "Phulwaria": ["Phulwariya", "Fulwaria"],
    "Bhore": ["Bhorey"], "Katiya": ["Katia"], "Manjha": ["Manja"], "Kalu Chhapra": ["Kalu Chapra", "Kaalu Chhapra"],
    "Meera Chhapra": ["Mira Chhapra", "Meera Chapra"], "Nirkhi Chhapra": ["Nirkhi Chapra"], "Babutola": ["Babu Tola"],
    "Panchdeuri": ["Panchdeori"], "Uchkagaon": ["Unchkagaon"], "Dewapur": ["Devapur"], "Nawadah": ["Nawada"],
    "Baikunthpur": ["Baikunthapur"], "Panditpur": ["Pandeetpur"],
}
GIVEN = [("Sita", "सीता"), ("Gita", "गीता"), ("Sunita", "सुनीता"), ("Rekha", "रेखा"), ("Anita", "अनीता"),
         ("Kamla", "कमला"), ("Pushpa", "पुष्पा"), ("Savitri", "सावित्री"), ("Lalita", "ललिता"), ("Meena", "मीना"),
         ("Usha", "उषा"), ("Radha", "राधा"), ("Shanti", "शांति"), ("Asha", "आशा"), ("Phoolmati", "फूलमती"),
         ("Ramesh", "रमेश"), ("Mohan", "मोहन"), ("Suresh", "सुरेश"), ("Dinesh", "दिनेश"), ("Anil", "अनिल"),
         ("Manoj", "मनोज"), ("Vijay", "विजय"), ("Santosh", "संतोष"), ("Ramji", "रामजी"), ("Bhola", "भोला"),
         ("Shivnath", "शिवनाथ"), ("Jagdish", "जगदीश"), ("Lakhan", "लखन"), ("Birju", "बिरजू"), ("Kishori", "किशोरी"),
         ("Umesh", "उमेश"), ("Naresh", "नरेश"), ("Prakash", "प्रकाश"), ("Arvind", "अरविंद"), ("Pappu", "पप्पू"),
         ("Munna", "मुन्ना"), ("Chandan", "चंदन"), ("Sonu", "सोनू"), ("Babloo", "बबलू"), ("Hari", "हरि")]
SURNAME = [("Devi", "देवी"), ("Kumari", "कुमारी"), ("Yadav", "यादव"), ("Prasad", "प्रसाद"), ("Ram", "राम"),
           ("Mahto", "महतो"), ("Paswan", "पासवान"), ("Sah", "साह"), ("Singh", "सिंह"), ("Manjhi", "मांझी"),
           ("Kushwaha", "कुशवाहा"), ("Ansari", "अंसारी"), ("Chaudhary", "चौधरी"), ("Rai", "राय")]
SITUATION = ["stuck on the roof", "water has entered the house", "the water is rising", "the road is cut",
             "trapped on the roof", "trapped inside the house, they can't get out"]
EXTRA = ["need medicine", "no food", "no drinking water", "an elderly man is there", "a newborn is there",
         "a pregnant woman is there", "medicines needed", "milk needed for the baby", "", "", ""]
NO_COUNT = ["the whole family is trapped, parents and children", "everyone in the house is on the roof",
            "all the family members are trapped, the water is rising", "everyone is shut in one room",
            "we are all trapped here, no help has come"]
VOLUNTEERS = ["Ravi", "Anjali", "Imran", "Pooja (NSS)", "Sanjay", "Neha", ""]
DONE = ["done", "Rescued", "✓", "safe", "DONE"]
SEEDED_DUPLICATES = [   # existing seeded cases (data/scenarios/BR/cases.yaml) the sheet reports again
    ("br-010", "98765 20010", "Barauli", 6), ("br-013", "+91-98765-20013", "Manjha", 7),
    ("br-030", "098765 20030", "Nawadah", 5), ("br-015", "9876520015", "Sidhwalia", 6)]


# Mumbai (MH, m88). LANDMARKED: each phrase measured on the MH map with the real location ladder (m88): it pins
# the ONE such landmark mapped near that place (step 4, a 300 m circle). VILLAGE_ONLY: places that resolve to
# themselves with no landmark said. Kurla West is left out: the live demo's family is there.
MH = {
    "seed": 2026_10_07, "districts": ("Mumbai Suburban", "Mumbai City"),
    "landmarked": {
        "Kurla East": ["near the church"], "Ghatkopar West": ["near the church"], "Govandi East": ["near the church"],
        "Malad West": ["near the church", "near the masjid"], "Wadala": ["near the church", "near the masjid"],
        "Mahul": ["near the school", "near the hospital", "near the station"], "Cheeta Camp": ["near the station"],
        "Andheri East": ["near the masjid"], "Powai": ["near the masjid"], "Santacruz West": ["near the masjid"],
        "Vikhroli Gaon": ["near the station", "near the masjid"], "Parel": ["near the masjid"],
        "Shivaji Nagar": ["near the church"], "Mankhurd Village": ["near the church"], "Goregaon East": ["near the masjid"],
    },
    "village_only": ["Kalina", "Saki Naka", "Jarimari", "Chembur", "Mankhurd", "Dharavi", "Sion Koliwada", "Bandra East",
                     "Kherwadi", "Chandivali", "Asalpha", "Tilak Nagar", "Deonar", "Mahim", "Nahur"],
    "variants": {
        "Ghatkopar West": ["Ghatkoper West"], "Govandi East": ["Gowandi East"], "Wadala": ["Vadala"],
        "Chembur": ["Chembure"], "Dharavi": ["Dharawi"], "Jarimari": ["Jari Mari"], "Saki Naka": ["Sakinaka"],
        "Kalina": ["Kaleena"], "Mankhurd": ["Mankhurdh"], "Kherwadi": ["Kherwaadi"], "Malad West": ["Malaad West"],
        "Cheeta Camp": ["Chita Camp"],
    },
    "given": [("Sunita", "सुनीता"), ("Rekha", "रेखा"), ("Anita", "अनीता"), ("Meena", "मीना"), ("Asha", "आशा"),
              ("Sangeeta", "संगीता"), ("Lata", "लता"), ("Vaishali", "वैशाली"), ("Pooja", "पूजा"), ("Shabana", "शबाना"),
              ("Rukhsana", "रुखसाना"), ("Mary", "मेरी"), ("Ramesh", "रमेश"), ("Suresh", "सुरेश"), ("Ganesh", "गणेश"),
              ("Santosh", "संतोष"), ("Vijay", "विजय"), ("Prakash", "प्रकाश"), ("Anil", "अनिल"), ("Mahesh", "महेश"),
              ("Sachin", "सचिन"), ("Rahul", "राहुल"), ("Imran", "इमरान"), ("Salim", "सलीम"), ("Joseph", "जोसेफ"),
              ("Francis", "फ्रान्सिस"), ("Dattatray", "दत्तात्रय"), ("Tukaram", "तुकाराम"), ("Sandeep", "संदीप"),
              ("Nitin", "नितीन"), ("Bharati", "भारती"), ("Kavita", "कविता"), ("Manisha", "मनीषा"), ("Yusuf", "यूसुफ"),
              ("Kishor", "किशोर"), ("Dinesh", "दिनेश"), ("Shankar", "शंकर"), ("Laxman", "लक्ष्मण"), ("Vinod", "विनोद"),
              ("Sunil", "सुनील")],
    "surname": [("Patil", "पाटील"), ("Shinde", "शिंदे"), ("Jadhav", "जाधव"), ("Pawar", "पवार"), ("Sawant", "सावंत"),
                ("Kamble", "कांबळे"), ("Gaikwad", "गायकवाड"), ("Chavan", "चव्हाण"), ("Shaikh", "शेख"), ("Khan", "खान"),
                ("Ansari", "अंसारी"), ("Fernandes", "फर्नांडिस"), ("Yadav", "यादव"), ("Gupta", "गुप्ता")],
    "seeded_duplicates": [("mh-018", "98765 30018", "Kalina", 7), ("mh-033", "+91-98765-30033", "Bandra East", 6),
                          ("mh-035", "098765 30035", "Mankhurd", 9), ("mh-017", "9876530017", "Dharavi", 5)],
    "relay_villages": ["Wadala", "Wadala", "Mahul", "Mahul", "Kurla East", "Kurla East", "Chembur", "Chembur"],
    "das": ("Wadala", "near the church", ("Patil", "पाटील")),
    "volunteers": ["Ravi", "Anjali", "Imran", "Pooja (NSS)", "Sanjay", "Neha", ""],
    "village_header": "Area",   # a Mumbai volunteer writes the neighbourhood under "Area"
}
BR = {
    "seed": 2026_10_05, "districts": ("Gopalganj",), "landmarked": LANDMARKED, "village_only": VILLAGE_ONLY,
    "variants": VARIANTS, "given": GIVEN, "surname": SURNAME, "seeded_duplicates": SEEDED_DUPLICATES,
    "relay_villages": ["Kalu Chhapra", "Kalu Chhapra", "Bhore", "Bhore", "Hathua", "Hathua", "Dewapur", "Dewapur"],
    "das": ("Meera Chhapra", "near the school", ("Das", "दास")), "volunteers": VOLUNTEERS,
}


def places(pack: str, districts) -> dict[str, dict]:
    gaz = ROOT / "data" / "scenarios" / pack / "gazetteer" / "places.csv"
    return {r["name"].strip(): r for r in csv.DictReader(gaz.open()) if r["district"] in districts}


def check_variants(gaz: dict[str, dict], variants: dict) -> None:
    """Each spelling must still match its own village best, at the ladder's fuzzy floor."""
    for name, variants in variants.items():
        for v in variants:
            scores = {p: fuzz.ratio(norm(v), norm(p)) for p in gaz}
            best = max(scores, key=scores.get)
            assert best == name and scores[best] >= FUZZY_MIN, f"{v!r} doesn't read as {name}: {best} {scores[best]}"


class Phones:
    """Unique synthetic numbers (98765 7xxxx), written the many ways volunteers write them."""
    def __init__(self, rng):
        self.rng, self.n = rng, 70000

    def new(self) -> str:
        self.n += self.rng.randint(1, 37)
        return f"98765{self.n:05d}"

    def written(self, digits: str) -> str:
        return self.rng.choice([f"{digits[:5]} {digits[5:]}", f"+91 {digits[:5]}-{digits[5:]}", f"0{digits[:5]} {digits[5:]}",
                                digits, f"+91{digits}", f"91-{digits[:5]}-{digits[5:]}", f"{digits[:5]}-{digits[5:]}"])

    @staticmethod
    def damaged(digits: str, resaved: bool) -> str:
        """What Excel leaves of 91XXXXXXXXXX: the 6-digit display, or that display read back in."""
        shown = f"{float('91' + digits):.5E}"            # "9.19877E+11": what a CSV saved from Excel holds
        return f"{float(shown):.0f}" if resaved else shown  # "919877000000": that, read back in and saved again


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default="BR", choices=["BR", "MH"])
    pack = ap.parse_args().pack
    cfg = {"BR": BR, "MH": MH}[pack]
    OUT = ROOT / "data" / "scenarios" / pack / "sheet"
    LANDMARKED, VILLAGE_ONLY, VARIANTS = cfg["landmarked"], cfg["village_only"], cfg["variants"]
    GIVEN, SURNAME, VOLUNTEERS = cfg["given"], cfg["surname"], cfg["volunteers"]
    rng = random.Random(cfg["seed"])
    gaz = places(pack, cfg["districts"])
    check_variants(gaz, VARIANTS)
    for v in [*LANDMARKED, *VILLAGE_ONLY]:
        assert v in gaz, v
    phones = Phones(rng)
    used: dict[str, list[str]] = {}     # village → given names already used there (kept pairwise distinct)

    def name_in(village: str) -> tuple[str, str]:
        taken = used.setdefault(village, [])
        options = [g for g in GIVEN if g[0] not in ("Ramesh", "Rajesh")
                   and all(fuzz.ratio(norm(g[0]), norm(t)) < FUZZY_MIN for t in taken)]
        g = rng.choice(options)
        taken.append(g[0])
        s = rng.choice(SURNAME)
        return f"{g[0]} {s[0]}", f"{g[1]} {s[1]}"

    def spelled(village: str) -> str:
        r = rng.random()
        if r < 0.25 and village in VARIANTS:
            return rng.choice(VARIANTS[village])
        if r < 0.33 and gaz[village]["name_hi"]:
            return village          # was the Devanagari spelling; English-only screens (D17)
        return village

    def headcount(n: int) -> str:
        return rng.choice([str(n), str(n), f"{n} people", f"{n - 1}-{n}", f"about {n}" if n > 6 else str(n),
                           {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}.get(n, str(n))])

    def remarks() -> str:
        bits = [rng.choice(SITUATION)] + [e for e in rng.sample(EXTRA, k=rng.choice([1, 2])) if e]
        return ", ".join(bits)

    households, rows = [], []

    def household(kind: str, village: str | None, landmark: str | None, n: int | None, *, phone=None, name=None) -> dict:
        h = {"id": f"H{len(households) + 1:03d}", "kind": kind, "village": village, "landmark": landmark, "people": n,
             "phone": phone or phones.new(), "name": name or (name_in(village or "-")), "remarks": remarks()}
        households.append(h)
        return h

    def row(h: dict, *, expect: str, phone_cell: str | None = None, damaged=False, hindi_name=False, status="",
            when="", count_cell: str | None = None, remarks_cell: str | None = None, note="", ai=False, relay=False,
            seed_case="", village_cell: str | None = None, landmark_cell: str | None = None) -> None:
        rows.append({
            "Name": h["name"][0],          # hindi_name still draws from the stream; the name stays in English
            "Mobile No": phone_cell if phone_cell is not None else phones.written(h["phone"]),
            "No. of people": count_cell if count_cell is not None else (headcount(h["people"]) if h["people"] else ""),
            "Village": village_cell if village_cell is not None else (spelled(h["village"]) if h["village"] else ""),
            "Location/Landmark": landmark_cell if landmark_cell is not None else (h["landmark"] or ""),
            "Remarks": remarks_cell if remarks_cell is not None else h["remarks"],
            "Time": when, "Status": status, "Volunteer": rng.choice(VOLUNTEERS),
            "_truth": {"household": h["id"], "kind": h["kind"], "village": h["village"] or "", "people": h["people"] or "",
                       "phone_damaged": damaged, "relay_phone": relay, "seed_case": seed_case, "needs_ai": ai,
                       "expect": expect, "note": note}})

    landmarked = list(LANDMARKED)

    def lm_household(kind: str, n: int | None = None) -> dict:
        v = rng.choice(landmarked)
        return household(kind, v, rng.choice(LANDMARKED[v]), n or rng.choice([3, 4, 5, 5, 6, 6, 7, 8]))

    # A/B · one household, several rows (the same calls collected twice or three times): same phone, same
    # landmark → Medium pins that overlap → auto-merge. Names may switch script; villages may be misspelt.
    for copies, count in ((2, 50), (3, 20)):
        for _ in range(count):
            h = lm_household(f"repeat{copies}")
            row(h, expect="new")
            for _ in range(copies - 1):
                row(h, expect="merged", hindi_name=rng.random() < 0.3,
                    count_cell=rng.choice([None, None, ""]), note="the same household again")
    # C · a repeat whose second phone was damaged by Excel: can't be identity → shown to a person, not merged.
    for i in range(4):
        h = lm_household("repeat_damaged_phone")
        row(h, expect="new")
        row(h, expect="to_check", phone_cell=Phones.damaged(h["phone"], resaved=i % 2 == 1), damaged=True,
            note="same household, but its phone was damaged by Excel: a likely duplicate for a person to confirm")
    # D · single households whose phone Excel damaged.
    for i in range(10):
        h = household("damaged_phone", rng.choice(VILLAGE_ONLY), None, rng.choice([3, 4, 5, 6]))
        row(h, expect="new", phone_cell=Phones.damaged(h["phone"], resaved=i % 3 == 0), damaged=True)
    # E · a relief volunteer's phone on 8 different families (a relay phone): never identity.
    relay = phones.new()
    for village in cfg["relay_villages"]:
        h = household("relay_phone", village, None, rng.choice([3, 4, 5, 6]), phone=relay)
        row(h, expect="new", relay=True, note="volunteer's phone, different family")
    # F · Ramesh and Rajesh of one surname: same place, landmark and headcount, different phones → refused, two cases.
    das_place, das_landmark, (sur, sur_hi) = cfg["das"]
    for given in (("Ramesh", "रमेश"), ("Rajesh", "राजेश")):
        h = household("das_pair", das_place, das_landmark, 5, name=(f"{given[0]} {sur}", f"{given[1]} {sur_hi}"))
        used.setdefault(das_place, []).append(given[0])
        row(h, expect="new", note="Ramesh ≠ Rajesh: never merged")
    # G · families already reported before the sheet (seeded cases): same phone and village → for a person.
    for key, phone_cell, village, n in cfg["seeded_duplicates"]:
        h = household("seeded_duplicate", village, None, n, phone=phone_cell.replace(" ", "").replace("-", "")[-10:])
        row(h, expect="to_check", phone_cell=phone_cell, seed_case=key, village_cell=village,
            note=f"already reported as seed case {key}; village-only pins can't auto-merge (D10)")
    # H · no place at all.
    for _ in range(3):
        h = household("no_location", None, None, rng.choice([3, 4, 5]))
        row(h, expect="to_check", remarks_cell=rng.choice(["we are trapped, please come quickly", "there is a lot of water, we need help",
                                                          "children and elderly people are trapped"]), note="no village: needs a person")
    # I · old reports (dates long before any demo run), one with a day/month that reads both ways.
    for when in ("01/10/2026 06:30", "02/10/2026 21:10", "03/10 11:20"):
        h = household("old_report", rng.choice(VILLAGE_ONLY), None, rng.choice([3, 4, 5]))
        row(h, expect="to_check", when=when, note="old report: confirm before sending a team")
    # J · rows the rules can place but not count: the language model is asked about these.
    for _ in range(19):
        h = household("needs_ai", rng.choice(VILLAGE_ONLY + landmarked), None, None)
        row(h, expect="new", count_cell="", remarks_cell=rng.choice(NO_COUNT), ai=True,
            note="no number of people the rules can read")
    # K · already done (rescued) before the sheet reached the desk → closed history.
    for _ in range(8):
        h = household("done", rng.choice(VILLAGE_ONLY), None, rng.choice([2, 3, 4, 5]))
        row(h, expect="history", status=rng.choice(DONE))
    # L · everyone else: one row each, some by a landmark, some by village only.
    while len(rows) < ROWS:
        if rng.random() < 0.4:
            h = lm_household("single")
        else:
            h = household("single", rng.choice(VILLAGE_ONLY), None, rng.choice([2, 3, 4, 5, 6, 7, 8, 9]))
        row(h, expect="new")

    # Shuffle, but keep each household's first row first (the "first" is what the others merge into).
    rng.shuffle(rows)
    seen: set[str] = set()
    for r in rows:
        t = r["_truth"]
        if t["expect"] in ("new", "merged") and t["kind"].startswith("repeat"):
            t["expect"] = "merged" if t["household"] in seen else "new"
        if t["kind"] == "repeat_damaged_phone":
            first = t["household"] not in seen
            if first and t["phone_damaged"]:   # the damaged copy came first: the intact one is the likely duplicate
                t["expect"] = "new"
            elif not first:
                t["expect"] = "to_check"
        seen.add(t["household"])

    OUT.mkdir(parents=True, exist_ok=True)
    headers = ["S.No", "Name", "Mobile No", "No. of people", "Village", "Location/Landmark", "Remarks", "Time", "Status", "Volunteer"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")     # Excel's line endings
    w.writerow([cfg.get("village_header", h) if h == "Village" else h for h in headers])
    for i, r in enumerate(rows, start=1):
        w.writerow([i, *(r[h] for h in headers[1:])])
    (OUT / "volunteer_sheet.csv").write_text(buf.getvalue(), encoding="utf-8")
    with (OUT / "ground_truth.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["row", "household", "kind", "village", "people", "phone_damaged", "relay_phone", "seed_case",
                "needs_ai", "expect", "note"]
        g = csv.DictWriter(f, fieldnames=cols)
        g.writeheader()
        for i, r in enumerate(rows, start=2):        # Excel row numbers: the header is row 1
            g.writerow({"row": i, **r["_truth"]})
    expect = Counter(r["_truth"]["expect"] for r in rows)
    print(f"wrote {len(rows)} rows, {len(households)} households → {OUT.relative_to(ROOT)}")
    print("expected:", dict(expect), "· damaged phones:", sum(r["_truth"]["phone_damaged"] for r in rows),
          "· needs AI:", sum(r["_truth"]["needs_ai"] for r in rows))


if __name__ == "__main__":
    main()
