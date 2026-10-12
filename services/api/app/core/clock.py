"""Times shown to people are India time (IST). The database clock (UTC) is the only clock for logic."""

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def hhmm(dt: datetime) -> str:
    return dt.astimezone(IST).strftime("%H:%M")


def hhmmss(dt: datetime) -> str:
    return dt.astimezone(IST).strftime("%H:%M:%S")
