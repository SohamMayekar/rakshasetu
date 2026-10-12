# providers · the two AI steps, behind small interfaces

- **What it does:** `app/providers/stt.py` (Sarvam Saaras → Groq whisper-large-v3) and `app/providers/llm.py` (Groq gpt-oss-120b → Gemini Flash) each run a primary → fallback chain (`run_chain`), recording every attempt for the receipt. With no keys every provider is *skipped*, not errored; the keyword path then creates the case.
- **Key tables:** `provider_usage` (calls/tokens/audio seconds per minute and per day), `extraction_cache`, `runtime_flags` (the "language model off" switch).
- **The tricky rule:** calls stop at **80% of a free cap** (`providers.free_caps` in the config), then the next provider takes over. Fixture mode (`PROVIDER_MODE=fixture`, used by tests) never touches the network: STT reads recorded transcripts from `data/fixtures/stt/<sha256>.json` and the receipt says `fixture`.
- **Honesty:** the LLM is asked for one thing, the closed extraction JSON (strict `json_schema` on Groq). It has no tools and no priority field.
- **How to show it:** `make provider-check` (OK / BLOCKED / FAILED per provider, synthetic input only).
