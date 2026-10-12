"use client";

// The design system on one page (local listener only; Caddy doesn't route /ui on the public address).
// Every desk, responder and reporter screen is built from these pieces.

import { CopyCheck, Inbox, Timer } from "lucide-react";

import { Because, Button, Caption, Card, ChannelTag, Check, Chip, CircleLegend, Empty, Estimate, IconWell, MethodChip, NewPill, Pill, Priority, PriorityWell, Receipt, Section } from "@/components/ui";

const RECEIPT = [
  { step: "STT", by: "AI", detail: "Saaras 2.1 s" },
  { step: "extract", by: "AI", detail: "6 fields" },
  { step: "quotes ✓", by: "Rule", detail: "" },
  { step: "place", by: "Rule", detail: "Medium" },
  { step: "P1", by: "Rule", detail: "" },
];

export default function DesignSystem() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-[28px] font-semibold tracking-tight">Design system</h1>
      <p className="mt-1 text-sm text-ink-2">Ink on paper, on a soft canvas. Hue means priority, and only priority; it is always also text and a shape. &ldquo;Needs you&rdquo; is ink inversion; stale is fade.</p>
      <Card className="mt-6 px-6">

      <Section title="Surfaces">
        <div className="flex flex-wrap items-center gap-3">
          <IconWell icon={Inbox} /><IconWell icon={CopyCheck} /><IconWell icon={Timer} tone="ink" label="a broken promise: ink, never colour" />
          <Pill>Live</Pill>
        </div>
        <p className="mt-2 text-xs text-ink-3">White cards (20 px radius, a hairline and a whisper of shadow) on the warm canvas; icons sit in round wells; buttons are pills.</p>
      </Section>

      <Section title="Priority">
        <div className="flex gap-6 text-lg"><Priority level="P1" /><Priority level="P2" /><Priority level="P3" /><Priority level="P4" /></div>
        <div className="mt-3 flex gap-3"><PriorityWell level="P1" /><PriorityWell level="P2" /><PriorityWell level="P3" /><PriorityWell level="P4" /></div>
        <Because>trapped + water entering · trapped + elderly</Because>
      </Section>

      <Section title="Chips">
        <div className="flex flex-wrap gap-2">
          <Chip tone="attention">contact overdue 3:10</Chip><Chip tone="attention">needs location</Chip>
          <Chip>possible duplicate</Chip><Chip tone="quiet">unchecked P1</Chip>
        </div>
        <p className="mt-2 text-xs text-ink-3">At most one attention chip per row, ranked: contact overdue / disputed &gt; needs location &gt; unchecked P1 &gt; possible duplicate &gt; low credibility.</p>
      </Section>

      <Section title="Receipts">
        <div className="space-y-2 text-sm">
          <p className="flex items-center gap-2"><Check state="checked" /> 6 people <MethodChip method="ai" /> <span className="text-ink-3">&ldquo;6 people are stuck on the roof&rdquo;</span></p>
          <p className="flex items-center gap-2"><Check state="unchecked" /> medicine <MethodChip method="rule" /> <span className="text-ink-3">&ldquo;they need medicine&rdquo;</span></p>
          <p className="flex items-center gap-2"><Check state="amber" /> elderly <MethodChip method="ai" /> <span className="text-ink-3">quote not found in the transcript</span></p>
          <p className="flex items-center gap-2"><Check state="checked" /> pin moved <MethodChip method="human" /> <MethodChip method="partner" /> <MethodChip method="fixture" /></p>
          <div className="flex items-center gap-2"><ChannelTag channel="voice" /><Receipt steps={RECEIPT} /></div>
          <p>People: <Estimate value={6} kind="estimated" /> · <Estimate value={4} kind="stated" /> · <Estimate value={null} /></p>
        </div>
      </Section>

      <Section title="Where">
        <CircleLegend />
        <p className="mt-2 text-xs text-ink-3">Circles always, never a bare pin. Dashed when Low.</p>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary">Assign</Button><Button>Heard on radio</Button><Button>Extend</Button>
          <Button size="sm">Reassign → Fire &amp; Rescue Boat 5 · 2.1 km · boat</Button><Button variant="quiet">Undo</Button>
        </div>
        <div className="mt-4 max-w-sm"><Button variant="primary" size="field">Acknowledge</Button></div>
      </Section>

      <Section title="Queue states">
        <NewPill count={47} onShow={() => {}} />
        <Empty>Nothing needs you. <span className="tabular">124</span> households have a live owner.</Empty>
      </Section>

      <Section title="Type">
        <p className="text-3xl font-semibold tracking-tight tabular">BR-214</p>
        <p className="text-sm">In Thawe village, behind the Durga temple, near the bridge, 6 people are stuck on the roof.</p>
        <p className="tabular text-sm text-ink-2">0123456789 · 14:32 · 2.1 km</p>
      </Section>

      </Card>
      <Caption text="A call-taker pasted a forwarded message. Rules found the same village, landmarks and headcount: it was folded into BR-214." />
    </main>
  );
}
