// "Needs you now" rows as the API computes them (GET /v1/queue): who needs a person, why, and the next step.

export type QueueRow = {
  id: number; public_id: string; priority: "P1" | "P2" | "P3" | "P4"; status: string; version: number;
  line1: string | null; line2: string; because: string; chip: string | null; broken: boolean;
  action: { kind: "radio" | "pin" | "match" | "check" | "assign" | "open"; label: string; target?: string };
};

export type Queue = { rows: QueueRow[]; on_it: number; rescued_closing: number; closed: number; open: number };
