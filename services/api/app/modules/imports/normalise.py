"""Row normalisation (PRD F-D3 step 3). Pure functions; each returns the value and any flag it raised.

- Phones → E.164. **Excel-damage guard:** Excel shows numbers of 12+ digits in exponential notation and keeps
  15 significant digits (VERIFIED, Microsoft support). A phone like "9.19877E+11", or one ending in 4+ zeros,
  has lost digits: it becomes null, is flagged "phone damaged by Excel", and is NEVER used as identity.
- Headcounts: "six", "5-6" → 6 (estimated), "about 10" → 10 (estimated), "6 log" → 6.
- Dates: several formats; an ambiguous one ("03/10") takes the reading closest before the import, flagged.
"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.phones import normalise as normalise_phone

IST = ZoneInfo("Asia/Kolkata")
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4,
         "paanch": 5, "panch": 5, "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10}


def phone(raw: str) -> tuple[str | None, str | None]:
    """(E.164 or None, flag or None)."""
    s = (raw or "").strip()
    if not s:
        return None, None
    if re.fullmatch(r"\d+(\.\d+)?[eE][+-]?\d+", s.replace(" ", "")):
        return None, "phone damaged by Excel"
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 10 and digits.endswith("0000"):
        return None, "phone damaged by Excel"
    e164 = normalise_phone(s)
    return (e164, None) if e164 else (None, "phone not readable")


def headcount(raw: str) -> tuple[int | None, str | None]:
    """(count, 'stated' | 'estimated' | None)."""
    s = (raw or "").strip().lower()
    if not s:
        return None, None
    m = re.search(r"(\d{1,4})\s*(?:-|–|to|se)\s*(\d{1,4})", s)
    if m:
        return max(int(m.group(1)), int(m.group(2))), "estimated"
    estimated = bool(re.search(r"about|approx|around|lagbhag|kareeb|~|\+", s))
    m = re.search(r"\d{1,4}", s)
    if m:
        return int(m.group(0)), "estimated" if estimated else "stated"
    for w, n in WORDS.items():
        if re.search(rf"\b{w}\b", s):
            return n, "estimated" if estimated else "stated"
    return None, None


_DMY = re.compile(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2}|\d{4}))?(?:,?\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]m)?)?",
                  re.IGNORECASE)
_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]m)?", re.IGNORECASE)
_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d",
            "%d %b %Y %H:%M", "%d %b %Y", "%d %b %H:%M", "%d %B %Y"]


def _hour(h: int, ampm: str | None) -> int:
    if ampm:
        return h % 12 + (12 if ampm.lower() == "pm" else 0)
    return h


def when(raw: str, imported_at: datetime) -> tuple[datetime | None, str | None]:
    """(time in IST, flag). Sheets are local time. A day/month that could be read either way ("03/10") takes the
    reading closest BEFORE the import, and is flagged so a person can see the choice."""
    s = (raw or "").strip()
    if not s:
        return None, None
    now = imported_at.astimezone(IST)
    latest = now + timedelta(minutes=5)
    m = _DMY.fullmatch(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        y = m.group(3)
        years = [int(y) + (2000 if len(y) == 2 else 0)] if y else [now.year, now.year - 1]
        hh, mm = _hour(int(m.group(4) or 0), m.group(6)), int(m.group(5) or 0)
        options = []
        for day, month in ((a, b), (b, a)):
            for year in years:
                try:
                    d = datetime(year, month, day, hh, mm, tzinfo=IST)
                except ValueError:
                    continue
                if d <= latest:
                    options.append(d)
        if not options:
            return None, "time not readable"
        either_way = a <= 12 and b <= 12 and a != b      # day/month could be read both ways: say which we chose
        return max(options), ("date read as the closest before the import" if either_way else None)
    m = _TIME.fullmatch(s)
    if m:   # a time only: today, or yesterday if that time hasn't come yet
        d = now.replace(hour=_hour(int(m.group(1)), m.group(3)) % 24, minute=int(m.group(2)), second=0, microsecond=0)
        return (d if d <= latest else d - timedelta(days=1)), None
    for fmt in _FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if "%Y" not in fmt:
            dt = dt.replace(year=now.year)
        dt = dt.replace(tzinfo=IST)
        return (dt, None) if dt <= latest else (None, "time not readable")
    return None, "time not readable"


DONE_WORDS = re.compile(r"^\s*(done|rescued|resolved|closed|safe|✓|✔|yes|ho gaya|bacha liya)\s*$", re.IGNORECASE)


def status_done(raw: str) -> bool:
    return bool(DONE_WORDS.match(raw or ""))


OLD_AFTER = timedelta(hours=12)


def normalise_row(cells: list[str], headers: list[str], mapping: dict[str, str], imported_at: datetime) -> dict:
    """One sheet row → the values the import uses, each from a mapped column, plus every flag raised."""
    by_field: dict[str, str] = {}
    for h, v in zip(headers, cells, strict=False):
        f = mapping.get(h)
        if f and f not in ("ignore", "unknown") and v:
            by_field[f] = v
    flags: list[str] = []
    e164, pflag = phone(by_field.get("phone", ""))
    count, count_kind = headcount(by_field.get("headcount", ""))
    at, tflag = when(by_field.get("time", ""), imported_at)
    for f in (pflag, tflag):
        if f:
            flags.append(f)
    if at and at < imported_at - OLD_AFTER:
        flags.append("old report: confirm before sending a team")
    # The text the keyword extractor reads: every mapped free-text column, in a fixed order.
    text = " · ".join(by_field[f] for f in ("location", "village", "district", "needs", "notes") if by_field.get(f))
    return {"name": by_field.get("name"), "phone": e164, "headcount": count, "headcount_kind": count_kind,
            "village": by_field.get("village"), "district": by_field.get("district"), "time": at,
            "done": status_done(by_field.get("status", "")), "text": text, "flags": flags}
