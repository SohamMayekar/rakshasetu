import pytest

from app.core.phones import decrypt, mask, normalise, protect


@pytest.mark.parametrize("raw,expected", [
    ("+91 98765 43210", "+919876543210"),
    ("098765-43210", "+919876543210"),
    ("9876543210", "+919876543210"),
    ("0091 9876543210", "+919876543210"),
    ("919876543210", "+919876543210"),
    ("9.19877E+11", None),      # Excel damage: the digits are gone
    ("12345", None),
    ("", None),
    (None, None),
    ("5876543210", None),       # Indian mobiles start 6-9
])
def test_normalise(raw, expected):
    assert normalise(raw) == expected


def test_mask_and_roundtrip():
    p = protect("+91 98765 43210")
    assert p["masked"] == mask("+919876543210") == "98xxxxxx10"
    assert decrypt(p["enc"]) == "+919876543210"
