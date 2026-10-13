# WhatsApp: the option we can offer (designed, not built)

**Status: not built.** The platform reads *forwarded* WhatsApp messages today (a volunteer pastes them into the desk
form, or sends them through the signed partner interface). A live WhatsApp number, where a family messages the desk
directly, is designed and the server is shaped for it, but it is **not switched on**: `whatsapp_channel: false` in
`services/api/config/flags.yaml`. Say exactly that on stage.

## Why it is worth saying
- It is where people already are. A relative far away will message a number before they open a web page.
- The hard part, turning a messy message into one case with its quotes, is already built. A WhatsApp message is one
  more way in, not a new system.
- It needs no app install and works on a basic phone with patchy data, which is when people use WhatsApp most.

## How it would work (small, on purpose)
1. A family or a relative sends a text or a voice note to the desk's WhatsApp number.
2. WhatsApp's Cloud API calls `POST /v1/ingest/whatsapp` with a signed request (`X-Hub-Signature-256`, checked over the raw bytes, same discipline as partner calls).
3. The channel adapter turns it into a Canonical Report (`channel: whatsapp`) and calls `intake.accept()`. The message
   id (`wamid`) is the idempotency key, so a retry from WhatsApp never makes two reports.
4. From there nothing is different: voice notes go through speech-to-text, text through the same word rules and
   quote-backed extraction, then dedupe, location, rules-based priority, one case, one owner.
5. The family gets **one fixed reply**: "Your report is registered. You don't need to remember anything." plus their
   case number. Never generated text, never a promise of arrival.
6. Later, inside WhatsApp's free 24 hour window: "Is that right?" for the rescue confirmation, at most once, asked
   only of family reporters. Silence never closes, escalates or lowers anything.

## What already exists
| Piece | Where |
|---|---|
| Forwarded messages as a channel, de-duplicated and marked as forwards | desk form · `POST /v1/ingest/reports` |
| Channel adapter registry (one module per channel) | `services/api/app/channels/` |
| Signed-webhook discipline (raw-byte HMAC, replay window, rate cap, log) | `services/api/app/channels/partner.py` |
| A job lane for WhatsApp and partner traffic | `config/rakshasetu.config.yaml` → `lanes` |
| Environment variables for the Cloud API test number | `.env.example` (`WHATSAPP_*`) |
| Feature flag, off | `config/flags.yaml` → `whatsapp_channel` |

## What is left to build (about half a day with a test number)
- The `whatsapp` adapter and the webhook route (verify token handshake, signature check, `wamid` de-dup).
- Voice notes: fetch the media, hand it to the same speech-to-text chain as the reporter page.
- The fixed reply and, optionally, the "Is that right?" template inside the 24 hour window.
- A Meta developer account and a Cloud API **test number** (free, limited to listed recipients).

## Honest limits (say these before anyone asks)
- **Groups are closed to us.** WhatsApp's API cannot read a group. A volunteer can export a group chat and upload it as a sheet; that path exists.
- **A test number only talks to listed phones.** Reaching the public needs a verified business number and Meta's approval. That is an organisation step, not a code step.
- **Replies outside 24 hours need an approved template.** We would only use the fixed reply and the single follow-up question.
- **It is not encrypted from us.** WhatsApp is a delivery channel. Phone numbers are still encrypted at rest and masked everywhere on the desk.
- **No location pin is trusted blindly.** A shared location is treated as one more clue and drawn as a circle, like everything else.

## Pitch lines
- "A family does not need our link. They can message a number they already know. It becomes the same one case, with the same one team, as a call or a form."
- "It is designed and the server is shaped for it. It is not switched on, and we will not show you a number that is not live."
- "The expensive part, reading a frightened message honestly, is already built. WhatsApp is one more way in."
- If asked about groups: "WhatsApp does not let any system read a group. A volunteer can export the chat and we take it in as a sheet."

## Where the site says it
- The landing page's **"Many ways in, one stream of cases"** card (WhatsApp shown as a dashed, **Planned** chip) and its FAQ entry "Can people report on WhatsApp?".
- `docs/BRIEF.md`, under "Not there, and said so".
