# Product

<!-- impeccable:product-schema 1 -->

## Platform

web (a landing page, a national desk, a team phone app, a no-login help page and a family status page)

## Users

- **People and families asking for help**, including a relative far away, from any phone, in their own language.
- **District duty officers and call-takers**, who coordinate a district's response.
- **The national admin / state desk**, who sees every incident and starts, stands down and closes them.
- **Responding teams** of any kind (fire, rescue, medical, volunteer, police, engineering, relief) on a phone or by radio.
- **Partners**, who send reports and sensor readings through a signed interface.

The landing page speaks to people asking for help and to those who answer, equally.

## Product Purpose

RakshaSetu is a **national incident command platform**. It accepts heterogeneous events (voice, typed calls, forwarded messages, volunteer spreadsheets, partner updates, sensor readings), turns each family or incident into **one case**, assigns **one accountable team**, keeps a timeline and its evidence, exposes a **live operational picture** across every incident, and follows each case until the people are **confirmed safe**.

## Positioning

- One case per family, one owner per case, duplicate reports joined with their reasons shown (and a look-alike kept apart).
- A quiet team is noticed and raised to a person, never reassigned automatically.
- AI is limited to speech-to-text and extracting facts **with their exact quotes**; rules rank and people decide. With no AI keys, every case is still created.
- One national desk, scoped in the database: a duty officer sees only their districts; the admin sees all.
- Not tied to a city, a disaster type or a team type: an incident is a form; a team is a form with a capability catalog.

## Operating Context

Active disasters of any kind: floods, cyclones, landslides, fires, gas leaks, building collapses, earthquakes and road accidents. Networks are often down: a request is saved on the phone and sent when signal returns. The product runs on a self-hosted stack with optional provider integrations and fallbacks, at no paid-service cost.

## Capabilities and Constraints

- A no-login help page (voice or text, with an optional call-back number, offline-safe), a family status page, a team phone app, one national desk (queue, map, case panel), Cases, Teams (add teams), Alerts, Sheets, Sensors, Incidents (lifecycle), and an audit History.
- Reports can arrive as voice, text, forwarded messages, volunteer sheets, partner updates or signed sensor readings. Facts keep their source quotes.
- Assignments have one owner. Overdue teams are surfaced to officers and are not automatically reassigned. Completion is the team's headcount plus the family's confirmation.
- Dispatch requires a capability only where the job cannot be done without it (a boat for water, heavy lift for a collapse); everything else is preferred, so an officer always decides.
- Languages: voice is transcribed by Sarvam (many Indian languages); Hindi, Hinglish, Marathi and English are read by word rules; other languages are read when AI keys are set. Screens are English.
- **Not built, and said so:** the live WhatsApp number (designed), the phone-to-phone Bluetooth relay (designed and shown as a simulation), real sensor instruments (the demo's are simulated), screens in other languages.
- A clean start has **no demo data**; the sample packs (Mumbai, Bihar, Odisha, Himachal) are optional and synthetic. Demo time may run 60 times faster and is labelled.

## Brand Commitments

Preserve the name RakshaSetu and the existing mark (a bridge's arch inside a shield). The landing page follows the soft, airy mood of the supplied reference: light sky, serif-italic accent words, white cards with tinted icon wells, and a drawn or photographed dawn behind the product.

## Evidence on Hand

`README.md`, `docs/BRIEF.md` (the brief, point by point), `docs/PITCH.md`, `docs/STATUS.md`, `docs/VERIFICATION.md`, `docs/LANGUAGES.md`, `docs/WHATSAPP.md` and `AI_USAGE.md`.

## Product Principles

- Keep every report and its source evidence together.
- Give each case one accountable team.
- Make uncertainty and missing contact visible to people who can act.
- Keep AI narrow, sourced and subordinate to rules and human decisions.
- Close the loop with the family, not only the rescue team's update.
- Never present a design as a feature: say "designed, not built".
