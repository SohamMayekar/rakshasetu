# keywords · the rule path that never needs AI

- **What it does:** `app/pipeline/keywords.py` reads the team-owned word lists in `services/api/dictionaries/hi.yaml` (Hindi in Devanagari, Hinglish, English) and fills the **same closed Extraction contract** the language model uses: headcount, hazards, needs, vulnerable people, village, landmarks with relation ("mandir ke peeche"), names, a callback phone.
- **Key files:** `dictionaries/hi.yaml` (regex patterns per field type), `app/pipeline/fields.py` (fields + provenance + the template summary).
- **The tricky rule:** every value keeps the caller's exact words as its quote, so the receipt works the same with a **Rule** chip. `medicine` (routine) and `medical_urgent` (behosh, saans nahi) are separate. A roof hazard absorbs "trapped"; "chhota bachcha" is an infant, not also a child.
- **When it runs:** it creates the case whenever the language model is off, failing or out of quota (F-C14), reads spreadsheet rows first, cross-checks the model (m19) and fills the desk's chips as you type (`POST /v1/ingest/desk/preview`).
- **How to show it:** demo control "language model off", then type the demo line: the case appears with Rule chips. On the 48 seed texts it matches the ground truth on headcount, hazards, needs and vulnerable people for 48/48.
