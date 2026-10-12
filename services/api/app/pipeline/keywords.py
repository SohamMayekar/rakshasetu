"""The keyword extractor (PRD §8.2): rules, ₹0, no network. Team-owned word lists in dictionaries/*.yaml.

Four jobs: (1) create the case when the language model is off, failing or out of quota; (2) the first pass
on spreadsheet rows; (3) cross-check the language model; (4) the desk's live chips as a call-taker types.

It returns the SAME closed Extraction contract as the language model, and every value carries the exact
words it came from (the quote), so the receipts work the same way, with a **Rule** chip instead of **AI**.
"""

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.contracts import (
    Extraction,
    HazardItem,
    Landmark,
    Location,
    NeedItem,
    PeopleCount,
    PersonName,
    Village,
    VulnerableItem,
)
from app.core.phones import normalise

DICT_DIR = Path(__file__).resolve().parent.parent.parent / "dictionaries"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN_WORD_EDGE = (r"(?<![A-Za-z])", r"(?![A-Za-z])")
NOT_A_VILLAGE = {"hum", "in", "calling", "ghar", "paani", "please", "mere", "my", "we", "the", "road", "school", "help"}


@lru_cache(maxsize=4)
def dictionary(lang: str = "hi") -> dict:
    return yaml.safe_load((DICT_DIR / f"{lang}.yaml").read_text())


def _quote(text: str, start: int, end: int) -> str:
    q = text[start:end].strip(" ,.;:-—।")
    return q[:300] if q else text[start:end][:300]


def _first(patterns: list[str], text: str):
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m and m.group(0).strip():
            return m
    return None


def _people(text: str, d: dict) -> PeopleCount | None:
    nouns = d["people_nouns"]
    words = "|".join(sorted(map(re.escape, d["number_words"]), key=len, reverse=True))
    est = d["estimate_words"]
    candidates = [
        (rf"(\d{{1,4}})\s*(?:-|–|to|se)\s*(\d{{1,4}})\s*{nouns}", "range"),
        (rf"(?:{est}\s*)?(\d{{1,4}})\s*{nouns}", "digits"),
        (rf"(?:{est}\s*)?(?<![\wऀ-ॿ])({words})\s*{nouns}", "words"),
    ]
    for pattern, kind in candidates:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        estimated = bool(re.match(est, m.group(0), re.IGNORECASE))
        if kind == "range":
            value, estimated = max(int(m.group(1)), int(m.group(2))), True
        elif kind == "digits":
            value = int(m.group(1))
        else:
            value = d["number_words"][next(k for k in d["number_words"] if k.lower() == m.group(1).lower())]
        if 0 < value <= 5000:
            # widen the quote to the surrounding phrase ("chhat pe 6 log fase hain")
            s = max(text.rfind(",", 0, m.start()), text.rfind(".", 0, m.start()), text.rfind("।", 0, m.start())) + 1
            e_candidates = [i for i in (text.find(",", m.end()), text.find(".", m.end()), text.find("।", m.end())) if i != -1]
            e = min(e_candidates) if e_candidates else len(text)
            if e - s > 80:
                s, e = m.start(), m.end()
            return PeopleCount(value=value, kind="estimated" if estimated else "stated", quote=_quote(text, s, e))
    return None


def _typed_items(section: dict, text: str, cls) -> list:
    items, spans = [], []
    for kind, patterns in section.items():
        m = _first(patterns, text)
        if m:
            items.append(cls(type=kind, quote=_quote(text, m.start(), m.end())))
            spans.append((kind, m.start(), m.end()))
    return items, spans


def _landmarks(text: str, d: dict) -> list[Landmark]:
    out = []
    names, rel_map = d["landmark_names"], d["relations"]
    for kind, pattern in d["landmarks"].items():
        wrapped = LATIN_WORD_EDGE[0] + pattern + LATIN_WORD_EDGE[1]
        for m in re.finditer(wrapped, text, re.IGNORECASE):
            start, end = m.start(), m.end()
            name = None
            before = re.search(rf"({names})(?:\s+(?:mata|maa|baba|ji))?\s*$", text[max(0, start - 25):start], re.IGNORECASE)
            if before:
                name = (before.group(0).strip() + " " + m.group(0)).strip()
                start -= len(before.group(0))
            relation = "unknown"
            for rel, rp in rel_map.items():
                after = re.match(rf"\s*{rp}", text[end:end + 20], re.IGNORECASE)
                if after:
                    relation, end = rel, end + after.end()
                    break
            out.append(Landmark(type=kind, name=name.title() if name and not DEVANAGARI.search(name) else name,
                                relation=relation, quote=_quote(text, start, end)))
            break   # one mention per landmark type is enough for the ladder
    return out[:6]


def to_latin(name: str) -> str:
    """Devanagari → a plain Latin spelling for fuzzy matching ("हथुआ" → "Hathua"). Latin input is unchanged."""
    if not DEVANAGARI.search(name):
        return name
    import unicodedata

    from indic_transliteration import sanscript
    iast = sanscript.transliterate(name, sanscript.DEVANAGARI, sanscript.IAST).replace("ṃ", "n")
    plain = "".join(ch for ch in unicodedata.normalize("NFD", iast) if unicodedata.category(ch) != "Mn")
    # Hindi drops the inherent final vowel: मीनापुर is "Minapur", not "Minapura".
    if "\u0915" <= name[-1] <= "\u0939" and plain.endswith("a"):
        plain = plain[:-1]
    return plain.title()


def _village(text: str, d: dict) -> Village | None:
    for p in d["village_cues"]:
        m = re.search(p, text.strip())
        if m and m.group(1).strip().lower() not in NOT_A_VILLAGE:
            name = m.group(1).strip()
            return Village(original=name, latin=to_latin(name), quote=_quote(text.strip(), m.start(), m.end()))
    return None


def _names(text: str, d: dict) -> list[PersonName]:
    surnames = "|".join(map(re.escape, d["surnames"]))
    out = []
    for m in re.finditer(rf"\b([A-Z][a-z]{{2,}})\s+({surnames})\b", text):
        out.append(PersonName(name=f"{m.group(1)} {m.group(2)}", quote=m.group(0)))
    return out[:10]


def _phone(text: str) -> str | None:
    m = re.search(r"(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}", text)
    return normalise(m.group(0)) if m else None


def extract_keywords(text: str, lang: str = "hi") -> Extraction:
    d = dictionary(lang)
    text = text or ""
    hazards, hz_spans = _typed_items(d["hazards"], text, HazardItem)
    if any(h.type == "trapped_on_roof" for h in hazards):          # on a roof IS trapped; say it once
        hazards = [h for h in hazards if h.type != "trapped_inside"]
    vulnerable, v_spans = _typed_items(d["vulnerable"], text, VulnerableItem)
    infant = next(((s, e) for k, s, e in v_spans if k == "infant"), None)
    if infant:                                                       # "chhota bachcha" is an infant, not also a child
        vulnerable = [v for v, (k, s, e) in zip(vulnerable, v_spans, strict=True)
                      if not (k == "child" and s < infant[1] and e > infant[0])]
    needs, _ = _typed_items(d["needs"], text, NeedItem)
    on_site = None
    if re.search(d["on_site_cues"], text, re.IGNORECASE):
        on_site = True
    elif re.search(d["remote_cues"], text, re.IGNORECASE):
        on_site = False
    return Extraction(
        language="hi" if DEVANAGARI.search(text) or re.search(r"\b(?:log|mein|hain|gaon|paani|chahiye)\b", text, re.I)
        else "en",
        people_count=_people(text, d), hazards=hazards, needs=needs, vulnerable=vulnerable,
        location=Location(village_or_locality=_village(text, d), district=None, state=None,
                          landmarks=_landmarks(text, d)),
        person_names=_names(text, d), callback_phone=_phone(text), reporter_on_site=on_site)
