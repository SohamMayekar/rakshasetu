"""Place-name normalisation for fuzzy matching across scripts and spellings (PRD F-L4 step 1).

"थावे", "Thawe" and "Thave" should meet; so should "Phulwaria" and "Phulavariya". We transliterate
Devanagari, lowercase, keep letters only, and fold the spellings Hindi place names vary on most:
long vowels (aa/ee/oo), v/w, and aspirated consonants (kh, gh, th, dh, bh, ph, chh).
"""

import re

from app.pipeline.keywords import to_latin

FOLD = [("chh", "c"), ("ch", "c"), ("kh", "k"), ("gh", "g"), ("th", "t"), ("dh", "d"), ("bh", "b"), ("ph", "p"),
        ("sh", "s"), ("aa", "a"), ("ee", "i"), ("oo", "u"), ("v", "w"), ("z", "j"), ("y", "i")]


def norm(name: str | None) -> str:
    if not name:
        return ""
    s = re.sub(r"[^a-z]", "", to_latin(name).lower())
    for a, b in FOLD:
        s = s.replace(a, b)
    return s
