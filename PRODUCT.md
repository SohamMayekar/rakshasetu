# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People and families seeking help during a disaster, and the district officers and rescue teams who coordinate and carry out that response. The landing page should address both audiences equally.

## Product Purpose

RakshaSetu is a district control room's rescue-request desk for the first two weeks of a disaster. It brings reports from voice clips, typed calls, forwarded messages, volunteer spreadsheets, and partner systems into a shared response workflow, then follows each family until the rescue team reports them safe and the family confirms it.

## Positioning

Each family becomes one case with one rescue team, with duplicate reports handled transparently and a quiet team noticed without automatic reassignment. AI is limited to speech-to-text and extracting facts with source quotes; rules and people make the decisions.

## Operating Context

The system is used during active disasters, including floods, cyclones, landslides, fires, collapses, and accidents. People can report from a phone. Officers coordinate from a district control room, and rescue teams use a phone app. The product is designed to operate on a self-hosted stack, with optional provider integrations and fallbacks.

## Capabilities and Constraints

- Public reporter flow, family status page, rescue-team phone app, district desk, and a state-level incidents view.
- Reports can arrive as voice, text, forwarded messages, volunteer sheets, or partner updates.
- A report's facts retain their source quotes. AI only performs speech-to-text and quote-backed extraction.
- Assignments have one owner. Overdue teams are surfaced to officers and are not automatically reassigned.
- Rescue completion is based on the team's headcount and the family's confirmation.
- Current screens are English. Hindi and Hinglish are read by the report rules, but multilingual screen support is not established.
- Demo people and phone numbers are synthetic. Demo time may run 60 times faster and is labelled. Live provider calls and operational outcome statistics are not established.

## Brand Commitments

Preserve the name RakshaSetu and the existing mark. The user explicitly chose the House of Al Hadeetha website in `ai-website-cloner-template` as the design and technology reference for this landing-page redesign.

## Evidence on Hand

The product and feature truth is documented in `README.md`, `docs/PRD.md`, `docs/STATUS.md`, `docs/VERIFICATION.md`, and `AI_USAGE.md`. A working demo follows a family report through assignment, team actions, rescue, and family confirmation. Product UI is present in `apps/web`.

## Product Principles

- Keep every family's report and source evidence together.
- Give each case one accountable rescue team.
- Make uncertainty and missing contact visible to people who can act.
- Keep AI narrow, sourced, and subordinate to rules and human decisions.
- Close the loop with the family, not only the rescue team's update.
