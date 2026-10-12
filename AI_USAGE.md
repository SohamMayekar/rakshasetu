# AI usage

Two separate things: the AI **inside RakshaSetu**, and the AI that **helped build it**. Both are described as they are. Overstating either would be a disqualification ground, and is not the point.

## 1. AI inside the product: exactly two jobs

| Job | What it does | Providers (free tiers, behind one interface, in this order) | When it is unavailable |
|---|---|---|---|
| **Speech to text** | A reporter's voice clip (≤ 30 s, transcoded to 16 kHz WAV) becomes text | Sarvam Saaras (`saaras:v4`), then Groq Whisper (`whisper-large-v3`) | The clip still becomes a case, marked **"audio only: listen"**, never lost (R12). A clip with a recorded transcript in `data/fixtures/stt/` uses it, and the receipt says **"Fixture · recorded transcript (not a live STT call)"** |
| **Fact extraction, with quotes** | The text becomes the closed Extraction v1 schema (`packages/contracts/extraction.schema.json`): headcount, hazards, needs, vulnerable people, village, landmarks, names, callback phone, **each with the caller's exact words as its quote**. The quote is checked against the text; a miss is shown amber | Groq `openai/gpt-oss-120b`, then Gemini `gemini-2.5-flash` | The **keyword rules** (`services/api/dictionaries/hi.yaml`) fill the same schema, and the chips say **Rule**. The case never waits on AI (8 s timeout, F-C14) |

**Everything else is rules and people, never a model:** priority (`config/rakshasetu.config.yaml`, team-owned rules, every level with its "because"), merges (a scored, explained suggestion; a person decides, and refusals like "Rajesh ≠ Ramesh" are rules), location (a gazetteer ladder with an honest circle), dispatch suggestions (nearest suitable unit), escalation (timers in the database), closure (the rescuers' headcount and the family's optional yes) and every reply (fixed sentences, never generated). The extraction schema has **no priority field and no free-text summary**, so a prompt-injected report can do nothing a lie couldn't. Phone numbers are replaced by placeholders before any text reaches a language model, and instruction-like words are flagged on the case (m57). The partner webhooks send facts, never names, numbers or words (m61).

**What was actually run in this build environment:** no STT or LLM key was available, so **no live AI call has been made**. Every case in the tests, the golden path and the screenshots was read by the keyword rules ("rules read 300, AI asked about 0") or from a recorded transcript, and the screens say so. The request formats for all four providers are tested offline against their documentation; the first live call happens when the team adds keys (`make provider-check`). This is listed as BLOCKED in `docs/STATUS.md`, not as done.

There is no agent, no agent framework and no model that decides, ranks, writes text shown to people or replies to a reporter.

## 2. AI used to build it

- **What a person still has to do** before the demo (record real voices, add keys, run on a real phone, measure on the demo laptop) is listed in `docs/VERIFICATION.md` and `docs/STATUS.md`. Every team member should be able to explain every module: `docs/TEACHBACK.md` has 20 questions to practise on, and `docs/modules/` has a short explainer per module.
- No other AI or idea tool was used for the product's design (per `CLAUDE.md`).
