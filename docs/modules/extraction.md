# extraction · AI proposes, rules check, people decide

- **What it does:** with the language model on, `app/pipeline/llm_extract.py` asks the model (Groq gpt-oss-120b → Gemini Flash) for the **closed extraction JSON**, validates it with Pydantic (one retry), then two rules run: the **quote check** (every quote must appear in the text, fuzzy ≥ 90, else the value is amber) and the **cross-check** (anything the keywords clearly found but the model dropped is kept, marked amber).
- **Key tables:** `extraction_cache` (same text → no second call), `jobs` (`llm.backfill`), `reports.receipt`.
- **The tricky rule:** the model never decides. It has no tools, no priority field and no free text; the report goes in a `<report>` block as data. If it is off, down, out of quota or returns output outside the contract, the keyword path creates the case **immediately**; if it was down (not merely unkeyed), a back-fill job re-reads the report when it returns and replaces only that report's unchecked Rule values.
- **Receipts:** each report records `extract · AI · 6 fields · groq/openai/gpt-oss-120b · 1.2 s` → `quotes ✓ · Rule`, or `language model off: 7 fields · Rule`.
- **How to show it:** hover a field: its quote lights up in the transcript; an amber ○ means "check this one".
