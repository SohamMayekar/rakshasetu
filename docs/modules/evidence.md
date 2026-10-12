# evidence · every item a stored file whose hash is in the audit chain (PRD F-C11, rule R16)

- **What it does:** each piece of evidence is a file in the content-addressed store (`files/ab/<sha256>`, hashed while it is written, never modified). Its sha256 goes into the audit chain in an `evidence.added` event (`app/modules/evidence/service.py`). The drawer re-hashes each file when it opens and shows "✓ matches the audit log" only if **both** hold: the file still hashes to its name, and that name is the hash the chain recorded.
- **The items:**

  | Type | Made when | What the drawer shows (each opens its stored file) |
  |---|---|---|
  | `audio` | a voice turn (reporter page, or the demo's recorded clip) | a player |
  | `transcript` | speech-to-text returns, once per report | who made it ("a recorded transcript, not a live speech-to-text call" in fixture mode) |
  | `message` | any typed, pasted, forwarded, partner or WhatsApp text, exactly as received | "The forward as received" |
  | `sheet_row` | a spreadsheet import (the whole file, plus the row number) | file name, row number, the row's cells |
  | `merge` | a merge, by rule or by a person (the decision, its signals and reasons) | "Merge record · BR-200 into BR-199" |
  | `rescue` | each rescue record, including an officer's radio record of the same trip | team, outcome, people taken, channel, **where the team was** and how far that is from the pin |
  | `radio` | an officer logs radio contact, one item on each case the team holds | team, channel, new ETA, note, who logged it |

- **Where the team was:** the responder app sends the phone's position with the rescue if it gets one within 3 s (it already did; m45). That position is also the team's new last known position, which dispatch distances use. Without one, the record says "the team's last known position" (the stored record keeps when that position was known). The demo reset's replayed rescues have no phone, so they say exactly that.
- **A report's items** (clip, transcript, message, sheet row) sit inside the report's card. **A case's own records** (rescue, radio log, merge) sit in the timeline where they happened.
- **Tamper checks (tested):** a file overwritten on disk shows ✗ (`file_ok` false; the chain still has the true hash); a row pointed at another stored file shows ✗ (`chain_ok` false). Files are served only inside the caller's scope (404 outside it), with `nosniff`.
- **Done when (PRD):** every item on the demo case opens its source and its hash matches the stored file and the audit event. Tested on the full replayed spine: 7 items (clip, transcript, the forward, the merge, the radio log, two rescue records).
- **Cost:** each text report now writes one small file. In the 50/s surge, the server's p50 to say "received" went from 22–29 ms to 33 ms; p95 stayed at 74 ms (one run).
