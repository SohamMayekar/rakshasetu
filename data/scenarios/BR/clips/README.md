# Recorded clips for "Play recorded clip" (PRD §16.4)

The demo control sends a clip from this folder **through the same live pipeline** as the reporter page
(transcode → speech-to-text → extraction → rules). Say so on stage.

| File | What it is |
|---|---|
| `son-line.synthetic.ogg` | **A synthetic voice, not a person.** espeak-ng 1.51 (`-v hi -s 135`) reading the demo line from `../README.md`, 11.8 s, Opus 24 kb/s. Made so the control works before the team records itself. |

- **Speech-to-text:** with an STT key the clip goes to the live provider. Without one, the pipeline falls back to the transcript in `data/fixtures/stt/<sha256 of the clip>.json`, and the case's receipt says **"Fixture · recorded transcript (not a live STT call)"**. For the synthetic clip that transcript is the exact text given to the synthesizer.
- **For the humans (pre-stage):** record the demo line in a real voice (and the other rehearsed inputs) as `.ogg`/`.webm`/`.mp3`/`.wav` files here. With STT keys present no transcript file is needed. Never present a fixture transcript as live recognition.
- All voices and words here are synthetic or the team's own; no real caller.
