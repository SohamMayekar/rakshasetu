export type MyCase = {
  id: number; public_id: string; priority: "P1" | "P2" | "P3" | "P4"; priority_reasons: string[]; summary: string | null;
  people_count: number | null; people_count_kind: string | null; needs: string[]; vulnerable: string[]; hazards: string[];
  location_text: string | null; location_method: string | null; location_confidence: string | null; radius_m: number | null;
  lat: number | null; lng: number | null; status: string; version: number; assignment_id: number;
  phase: "offered" | "acknowledged" | "reached"; state: "open" | "overdue"; eta_minutes: number | null;
  next_contact_due: string; demo_clock: boolean; created_at: string; distance_km: number | null;
};
export type MyTeam = { id: number; name: string; has_app: boolean; radio_channel: string | null; last_contact_at: string | null;
                       last_seen_at: string | null; incident: string };
