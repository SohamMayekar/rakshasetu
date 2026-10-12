"""Spreadsheet import, steps 1–3 (PRD F-D3): reading, header mapping, normalisation, the Excel-damage guard."""

import io
from datetime import UTC, datetime

import openpyxl
import pytest

from app.core.storage import path_for
from app.modules.imports import mapping, normalise, parse
from tests.conftest import login, needs_db, one, rows

AT = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)          # 14:30 IST


# --- the Excel-damage guard (T5) -----------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["9.19877E+11", "9.19877e+11", "9.18E+11", "9876500000", "919876500000", "+91 98765 00000"])
def test_phone_damaged_by_excel_is_null_and_flagged(raw):
    assert normalise.phone(raw) == (None, "phone damaged by Excel")


@pytest.mark.parametrize("raw,e164", [("98765 43210", "+919876543210"), ("098765-43210", "+919876543210"),
                                      ("+91 9876543210", "+919876543210"), ("919876543210", "+919876543210")])
def test_phone_to_e164(raw, e164):
    assert normalise.phone(raw) == (e164, None)


def test_phone_blank_and_unreadable():
    assert normalise.phone("") == (None, None)
    assert normalise.phone("call the pradhan") == (None, "phone not readable")


# --- headcounts and times --------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,want", [("6", (6, "stated")), ("6 log", (6, "stated")), ("six", (6, "stated")),
                                      ("5-6", (6, "estimated")), ("about 10", (10, "estimated")),
                                      ("lagbhag 8", (8, "estimated")), ("", (None, None)), ("many", (None, None))])
def test_headcount(raw, want):
    assert normalise.headcount(raw) == want


def test_ambiguous_date_takes_the_reading_closest_before_the_import():
    t, flag = normalise.when("03/10 11:20", AT)          # 3 Oct or 10 Mar: 3 Oct is closer before 12 Oct
    assert (t.month, t.day, t.hour, t.minute) == (10, 3, 11, 20)
    assert flag == "date read as the closest before the import"
    t, flag = normalise.when("10/12/2026", AT)           # 10 May or 12 Oct (today, before the import) → 12 Oct
    assert (t.month, t.day) == (10, 5) and flag


def test_unambiguous_and_other_times():
    t, flag = normalise.when("25/09/2026 14:05", AT)
    assert (t.month, t.day, t.hour) == (9, 25, 14) and flag is None
    t, _ = normalise.when("2026-10-12 16:25:00", AT)     # what openpyxl gives for an Excel date cell
    assert (t.day, t.hour, t.minute) == (5, 13, 40)
    t, _ = normalise.when("2:10 pm", AT)
    assert (t.day, t.hour, t.minute) == (5, 14, 10)
    t, _ = normalise.when("16:00", AT)                    # later than now → yesterday
    assert (t.day, t.hour) == (4, 16)
    assert normalise.when("next week", AT) == (None, "time not readable")
    assert normalise.when("25/12/2026", AT) == (None, "time not readable")   # in the future
    t, flag = normalise.when("05/12/2026", AT)           # 5 Dec is in the future; 12 May is the only reading left
    assert (t.month, t.day) == (5, 12) and flag


def test_normalise_row_flags_old_rows_and_builds_the_text():
    headers = ["Naam", "Mob", "Kitne log", "Gaon", "Location", "Remarks", "Samay", "Status"]
    m = mapping.propose(headers)
    n = normalise.normalise_row(["Sita Devi", "9.19877E+11", "5-6", "Thawe", "mandir ke paas", "dawai chahiye",
                                 "04/10/2026 01:00", "done"], headers, m, AT)
    assert n["phone"] is None and "phone damaged by Excel" in n["flags"]
    assert n["headcount"] == 6 and n["headcount_kind"] == "estimated"
    assert n["text"] == "mandir ke paas · Thawe · dawai chahiye"
    assert "old report: confirm before sending a team" in n["flags"]
    assert n["done"] is True


# --- header mapping ----------------------------------------------------------------------------------------------

def test_propose_maps_hindi_hinglish_and_english_headers():
    headers = ["S.No", "Naam", "Mob No", "Kitne log", "गाँव", "Location/Landmark", "Remarks", "Samay", "Volunteer", "Colour"]
    assert mapping.propose(headers) == {
        "S.No": "ignore", "Naam": "name", "Mob No": "phone", "Kitne log": "headcount", "गाँव": "village",
        "Location/Landmark": "location", "Remarks": "notes", "Samay": "time", "Volunteer": "ignore", "Colour": "unknown"}


def test_a_field_comes_from_one_column_only():
    assert mapping.propose(["Phone", "Mobile"]) == {"Phone": "phone", "Mobile": "unknown"}


def test_validate_refuses_bad_mappings():
    h = ["Naam", "Mob", "Gaon"]
    assert mapping.validate({"Naam": "name", "Mob": "phone", "Gaon": "village"}, h) == []
    assert mapping.validate({"Naam": "name", "Mob": "name", "Gaon": "village"}, h)        # a field twice
    assert mapping.validate({"Naam": "name", "Mob": "phone", "Gaon": "ignore"}, h)        # nothing to place a row
    assert mapping.validate({"Naam": "name", "Mob": "phone", "Gaon": "priority"}, h)      # not a field
    assert mapping.validate({"Naam": "name", "Mob": "phone"}, h)                          # a header left out


# --- reading files safely ----------------------------------------------------------------------------------------

def test_csv_utf8_with_hindi_and_bom():
    s = parse.read("s.csv", "﻿नाम,phone\nसीता देवी,9876543210\n".encode())
    assert s.headers == ["नाम", "phone"] and s.rows == [["सीता देवी", "9876543210"]]
    assert s.encoding == "utf-8-sig" and s.warnings == []


def test_csv_cp1252_is_read_and_flagged():
    s = parse.read("s.csv", "name,notes\nJosé,café roof\n".encode("cp1252"))
    assert s.encoding == "cp1252" and s.rows[0] == ["José", "café roof"]
    assert s.warnings


def test_csv_mojibake_is_flagged():
    s = parse.read("s.csv", "name,notes\nà¤¸à¥€à¤¤à¤¾,roof\n".encode())
    assert s.warnings


def _xlsx(rows_) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows_:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_reads_values_and_never_evaluates_formulas():
    data = _xlsx([["Naam", "Mob", "Kitne log", "Check"], ["Ram", 919876543210, 6, "=1+1"]])
    s = parse.read("s.xlsx", data)
    assert s.kind == "xlsx" and s.headers == ["Naam", "Mob", "Kitne log", "Check"]
    # The number is stored in full in .xlsx; the formula has no cached value and is NOT computed by us.
    assert s.rows == [["Ram", "919876543210", "6", ""]]


@pytest.mark.parametrize("data,err", [
    (b"a" * (parse.MAX_BYTES + 1), "5 MB"),
    (",".join(f"c{i}" for i in range(41)).encode() + b"\n" + b"x\n", "columns"),
    (b"name\n" + b"x" * 1001 + b"\n", "characters"),
    (b"name\n" + b"x\n" * 5001, "rows"),
    (b"\n\n", "empty"),
    (b"PK\x03\x04not really a zip", "xlsx"),
])
def test_caps_and_bad_files_are_refused_not_truncated(data, err):
    with pytest.raises(parse.SheetError, match=err):
        parse.read("s.csv", data)


# --- the endpoints -----------------------------------------------------------------------------------------------

SHEET = (b"S.No,Naam,Mob,Kitne log,Gaon,Location,Remarks,Samay\n"
         b"1,Sita Devi,9.19877E+11,5-6,Thawe,Durga mandir ke peeche,dawai chahiye,03/10 11:20\n"
         b"2,Ramesh Das,98765 43210,4,Thave,pul ke paas,chhat par,12/10/2026 13:00\n")


def _upload(client, data=SHEET, incident="BR", name="volunteers.csv"):
    return client.post("/v1/imports", files={"file": (name, data, "text/csv")}, data={"incident": incident})


@needs_db
def test_upload_stores_the_file_proposes_a_mapping_and_previews(seeded, client, app_db):
    login(client, "priya")
    r = _upload(client)
    assert r.status_code == 201, r.text
    imp = r.json()
    assert imp["status"] == "uploaded" and imp["rows_total"] == 2 and imp["file_kind"] == "csv"
    assert imp["proposed"]["Naam"] == "name" and imp["proposed"]["S.No"] == "ignore"
    assert path_for(imp["file_sha256"]).exists()
    first, second = imp["preview"]
    assert first["row"] == 2 and first["reads_as"]["phone"] is None and "phone damaged by Excel" in first["flags"]
    assert first["reads_as"]["headcount"] == 6 and first["reads_as"]["headcount_kind"] == "estimated"
    assert second["reads_as"]["phone"] == "98xxxxxx10"          # masked in the preview
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'import.uploaded' AND entity_id = :i",
               i=str(imp["id"])) == 1
    assert client.get(f"/v1/imports/{imp['id']}").json()["id"] == imp["id"]


@needs_db
def test_a_person_confirms_the_mapping(seeded, client, app_db):
    login(client, "priya")
    imp = _upload(client).json()
    bad = dict(imp["proposed"], Remarks="name")
    r = client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": bad})
    assert r.status_code == 422
    good = dict(imp["proposed"], Remarks="needs")
    r = client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": good})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "mapped" and r.json()["mapping"]["Remarks"] == "needs"
    ev = rows(app_db, "SELECT body::jsonb->'data' FROM events WHERE action = 'import.mapped' AND entity_id = :i",
              i=str(imp["id"]))
    assert ev and ev[0][0]["changed_from_proposal"] == ["Remarks"]


@needs_db
def test_imports_are_scoped(seeded, client):
    login(client, "priya")
    imp = _upload(client).json()
    login(client, "mkumar")                          # BR, but Muzaffarpur
    assert client.get(f"/v1/imports/{imp['id']}").status_code == 404
    assert client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": imp["proposed"]}).status_code == 404
    login(client, "spatra")                          # Odisha only
    assert _upload(client).status_code == 404
    login(client, "boat5")
    assert _upload(client).status_code == 403


@needs_db
def test_imports_exist_only_on_the_local_listener(seeded, client):
    login(client, "priya")
    r = client.post("/v1/imports", files={"file": ("s.csv", SHEET, "text/csv")}, data={"incident": "BR"},
                    headers={"X-RS-Listener": "public"})
    assert r.status_code == 404


@needs_db
def test_an_unreadable_sheet_is_refused_with_the_reason(seeded, client):
    login(client, "priya")
    r = _upload(client, data=b"PK\x03\x04garbage", name="s.xlsx")
    assert r.status_code == 422 and "xlsx" in r.json()["detail"]
    r = _upload(client, data=b"Naam,Mob\n")
    assert r.status_code == 422 and "no rows" in r.json()["detail"]
