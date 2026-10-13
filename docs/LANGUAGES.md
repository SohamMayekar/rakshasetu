# Languages: what it understands today, and how to add more

**Short answer:** yes, most Indian languages are possible, because speech goes through **Sarvam**, which is built
for them and detects the language itself (`language_code: unknown`). What differs is how far a report is *read* after
it is transcribed.

| Layer | What it covers | Needs |
|---|---|---|
| **Voice to text** | Sarvam Saaras (primary) with Groq Whisper as the fallback. Indian languages and English, language auto-detected. The transcript and the original audio are both kept. | `SARVAM_API_KEY` (and optionally `GROQ_API_KEY`) |
| **Reading the facts: word rules** | Hindi, Hinglish (Latin script), Marathi and English: people counts, hazards, needs, vulnerable people, landmarks, village cues. No AI, no network. | nothing |
| **Reading the facts: AI** | Any Indian language or English. The prompt names Hindi, Gujarati, Marathi, Bengali, Tamil and Hinglish and asks for the same closed schema, every value with its exact quote, which is then checked against the words. | `GROQ_API_KEY` or `GEMINI_API_KEY` |
| **Screens** | English (decision D17). | translation of the interface (not built) |

## What happens to a language the rules do not read
1. Voice is still transcribed (with a Sarvam key) and the report becomes a case with the original words.
2. With an AI key, the facts are extracted with quotes, checked, and the case is ranked like any other.
3. With no AI key, the case is created with its transcript and an "audio only / no details yet: listen or call back"
   summary, so a person at the desk reads it. **Nothing is lost.** It just sorts lower until someone reads it.

## Adding a language's word list (about an hour per language with a native reader)
Word rules live in `services/api/dictionaries/<lang>.yaml`, the same shape as `hi.yaml`: people nouns and number
words, hazard patterns, needs, vulnerable people, landmarks and place cues. `extract_keywords(text, lang)` already
takes the language. Steps:
1. Copy `hi.yaml` to `bn.yaml` (or `ta.yaml`, `te.yaml`, …), keep the keys, replace the patterns.
2. Have a native speaker read the patterns: a wrong word creates a false fact. Every value carries its quote, so a
   person can always see why.
3. Route by the language code the speech provider returns (`hi-IN`, `bn-IN`, `ta-IN`…) to that dictionary.
4. Add reports in that language to `data/eval/reports.yaml` and run `make read-eval` to measure.

## Honest claims for the pitch
- "Voice works across Indian languages through Sarvam. The word rules read Hindi, Marathi and English today and the
  AI path reads the rest. Screens are English for now."
- Do **not** claim a language count. The repository's own rules forbid it, and the real answer depends on the keys.
