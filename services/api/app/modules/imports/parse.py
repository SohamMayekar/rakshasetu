"""Reading a volunteer spreadsheet safely (PRD F-D3, rule R15).

- XLSX: openpyxl read-only with `data_only=True` (cell VALUES only; a formula is never evaluated by us),
  and defusedxml installed, which openpyxl uses to refuse XML entity attacks.
- CSV: UTF-8 (with or without a BOM), then cp1252; text that looks garbled is flagged.
- Caps: 5 MB, 5,000 rows, 40 columns, 1,000 characters per cell. Anything beyond is refused, not truncated
  silently.
"""

import csv
import io
import re
from dataclasses import dataclass, field

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLS = 40
MAX_CELL = 1000
MOJIBAKE = re.compile(r"Ã.|â€|à¤|Â")


class SheetError(Exception):
    pass


@dataclass
class Sheet:
    kind: str
    headers: list[str]
    rows: list[list[str]]
    encoding: str | None = None
    warnings: list[str] = field(default_factory=list)


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)          # 9876543210.0 → "9876543210"
    s = str(v).strip()
    if len(s) > MAX_CELL:
        raise SheetError(f"a cell is longer than {MAX_CELL} characters")
    return s


def _check_shape(headers: list[str], rows: list[list[str]]) -> None:
    if len(headers) > MAX_COLS:
        raise SheetError(f"more than {MAX_COLS} columns")
    if len(rows) > MAX_ROWS:
        raise SheetError(f"more than {MAX_ROWS} rows")


def read(file_name: str, data: bytes) -> Sheet:
    if len(data) > MAX_BYTES:
        raise SheetError("larger than 5 MB")
    if file_name.lower().endswith(".xlsx") or data[:2] == b"PK":
        return _xlsx(data)
    return _csv(data)


def _xlsx(data: bytes) -> Sheet:
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:
        raise SheetError(f"not a readable .xlsx file ({type(e).__name__})") from None
    ws = wb.worksheets[0]
    out: list[list[str]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i > MAX_ROWS + 1:
            raise SheetError(f"more than {MAX_ROWS} rows")
        if len(row) > MAX_COLS:
            raise SheetError(f"more than {MAX_COLS} columns")
        out.append([_cell(v) for v in row])
    wb.close()
    while out and not any(out[-1]):
        out.pop()
    if not out:
        raise SheetError("the sheet is empty")
    headers, rows = out[0], [r for r in out[1:] if any(r)]
    _check_shape(headers, rows)
    return Sheet("xlsx", headers, rows)


def _csv(data: bytes) -> Sheet:
    text, encoding = None, None
    for enc in ("utf-8-sig", "cp1252") if data.startswith(b"\xef\xbb\xbf") else ("utf-8", "cp1252"):
        try:
            text, encoding = data.decode(enc), enc
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise SheetError("couldn't read the text encoding")
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as e:
        raise SheetError(f"not a readable CSV ({e})") from None
    rows = [[_cell(c) for c in r] for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise SheetError("the sheet is empty")
    headers, body = rows[0], rows[1:]
    _check_shape(headers, body)
    warnings = []
    if encoding == "cp1252" or any(MOJIBAKE.search(c) for r in body[:200] for c in r):
        warnings.append("some text looks garbled (saved in a different encoding); check the preview")
    return Sheet("csv", headers, body, encoding=encoding, warnings=warnings)
