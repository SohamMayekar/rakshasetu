"use client";

// The building blocks on one page, for the team (local listener only; not linked from any screen). Every desk, team
// and phone screen is made from these pieces, so a change here shows everywhere.

import { CircleCheck, LifeBuoy, Siren } from "lucide-react";

import { Because, Button, Card, ChannelTag, Check, Chip, CircleLegend, Empty, Estimate, IconWell, MethodChip, NewPill, Pill, Priority, PriorityWell, Section } from "@/components/ui";

export default function BuildingBlocks() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-[28px] font-semibold tracking-tight">Building blocks</h1>
      <p className="mt-1 text-sm text-ink-2">Black on white. Colour is used for one thing only: how urgent a family is.</p>
      <Card className="mt-6 px-6">

      <Section title="How urgent">
        <div className="flex gap-6 text-lg"><Priority level="P1" /><Priority level="P2" /><Priority level="P3" /><Priority level="P4" /></div>
        <div className="mt-3 flex gap-3"><PriorityWell level="P1" /><PriorityWell level="P2" /><PriorityWell level="P3" /><PriorityWell level="P4" /></div>
        <Because>trapped and water coming in · an elderly person</Because>
        <p className="mt-2 text-xs text-ink-3">Always a word and a shape too, never colour alone.</p>
      </Section>

      <Section title="Numbers on the desk">
        <div className="flex flex-wrap items-center gap-3">
          <IconWell icon={Siren} /><IconWell icon={LifeBuoy} /><IconWell icon={CircleCheck} />
          <IconWell icon={Siren} tone="ink" label="lives at risk: black, never red" />
          <Pill><span className="size-2 rounded-full bg-ink" aria-hidden />Live</Pill>
        </div>
      </Section>

      <Section title="Labels on a row">
        <div className="flex flex-wrap gap-2">
          <Chip tone="attention">contact overdue 3:10</Chip><Chip tone="attention">where exactly?</Chip>
          <Chip tone="attention">not checked yet</Chip><Chip>maybe a repeat</Chip>
        </div>
        <p className="mt-2 text-xs text-ink-3">One label per row: the most important one.</p>
      </Section>

      <Section title="Where each fact came from">
        <div className="space-y-2 text-sm">
          <p className="flex items-center gap-2"><Check state="checked" /> 6 people <MethodChip method="ai" /> <span className="text-ink-3">&ldquo;6 people are stuck on the roof&rdquo;</span></p>
          <p className="flex items-center gap-2"><Check state="unchecked" /> medicine <MethodChip method="rule" /> <span className="text-ink-3">&ldquo;they need medicine&rdquo;</span></p>
          <p className="flex items-center gap-2"><Check state="amber" /> elderly <MethodChip method="ai" /> <span className="text-ink-3">these words are not in what they said: check</span></p>
          <p className="flex items-center gap-2"><Check state="checked" /> place moved <MethodChip method="human" /> <MethodChip method="partner" /> <MethodChip method="fixture" /></p>
          <p className="flex items-center gap-2"><ChannelTag channel="voice" /> <ChannelTag channel="whatsapp" /> <ChannelTag channel="spreadsheet" /> <ChannelTag channel="web_form" /></p>
          <p>People: <Estimate value={6} kind="estimated" /> (about) · <Estimate value={4} kind="stated" /> · <Estimate value={null} /> (not said)</p>
        </div>
        <p className="mt-2 text-xs text-ink-3">● checked by a person · ○ not checked yet · amber ○ check this one.</p>
      </Section>

      <Section title="Where the family is">
        <CircleLegend />
        <p className="mt-2 text-xs text-ink-3">Always a circle, never a dot: how sure we are of the place. Dashed when we only know the village.</p>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary">Send SDRF Boat 2</Button><Button>Heard from them</Button><Button>Mark checked</Button>
          <Button variant="quiet">Undo</Button>
        </div>
        <div className="mt-4 max-w-sm"><Button variant="primary" size="field">I&rsquo;ve reached them</Button></div>
        <p className="mt-2 text-xs text-ink-3">One main button per screen. Buttons on the team&rsquo;s phone are big enough for wet hands.</p>
      </Section>

      <Section title="The list">
        <NewPill count={47} onShow={() => {}} />
        <Empty>Nothing needs you. <span className="tabular">124</span> families have a team on it.</Empty>
        <p className="mt-2 text-xs text-ink-3">New rows wait behind the black pill, so the list never moves under your cursor.</p>
      </Section>

      <Section title="Text">
        <p className="text-3xl font-semibold tracking-tight tabular">BR-214</p>
        <p className="text-sm">In Thawe village, behind the Durga temple, near the bridge, 6 people are stuck on the roof.</p>
        <p className="tabular text-sm text-ink-2">0123456789 · 14:32 · 2.1 km</p>
      </Section>

      </Card>
    </main>
  );
}
