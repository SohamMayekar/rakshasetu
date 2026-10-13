"""Phone numbers (rule R17, PRD §13.4): normalised to E.164, encrypted at rest, matched by keyed HMAC,
and shown only masked (98xxxxxx21). A full number is revealed only through an audited action (P1).
"""

import base64
import hashlib
import hmac
import os
import re

from cryptography.fernet import Fernet

from app.settings import get_settings

_DIGITS = re.compile(r"\D+")
# A number said aloud and written down in Devanagari ("९८७६५…") is still a number.
_ASCII_DIGITS = str.maketrans("०१२३४५६७८९٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalise(raw: str | None) -> str | None:
    """'+91 98765-43210', '098765 43210', '9876543210' → '+919876543210'. Anything else → None."""
    if not raw:
        return None
    s = str(raw).strip().translate(_ASCII_DIGITS)
    if re.search(r"[eE][+-]?\d", s):  # Excel's exponential notation: digits already lost (see imports)
        return None
    digits = _DIGITS.sub("", s)
    if digits.startswith("0091"):
        digits = digits[4:]
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        return None
    return "+91" + digits


def phone_hash(e164: str) -> str:
    key = (os.environ.get("PHONE_HASH_KEY") or "dev-only-phone-hmac-key").encode()
    return hmac.new(key, e164.encode(), hashlib.sha256).hexdigest()


def mask(e164: str) -> str:
    """'+919876543210' → '98xxxxxx10'."""
    local = e164[-10:]
    return f"{local[:2]}xxxxxx{local[-2:]}"


def _fernet() -> Fernet:
    key = (os.environ.get("PHONE_ENC_KEY") or "").strip()
    if not key:
        # Development fallback: derive a key from SECRET_KEY. `make keys` prints a real one for .env.
        key = base64.urlsafe_b64encode(hashlib.sha256(get_settings().secret_key.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt(e164: str) -> str:
    return _fernet().encrypt(e164.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def protect(raw: str | None) -> dict:
    """Everything we store about a reporter's phone: {enc, hash, masked}, or all None."""
    e164 = normalise(raw)
    if not e164:
        return {"enc": None, "hash": None, "masked": None}
    return {"enc": encrypt(e164), "hash": phone_hash(e164), "masked": mask(e164)}
