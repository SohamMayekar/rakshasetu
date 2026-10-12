// Same-origin JSON calls to the API (Caddy routes /v1/* to it). The session is an httpOnly cookie, so
// there is no token here to steal. Mutations are JSON-only (the API refuses form posts: CSRF).

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const r = await fetch(path, {
    cache: "no-store",
    ...rest,
    headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  const body = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new ApiError(r.status, (body as { detail?: unknown })?.detail ?? body);
  return body as T;
}

export type Prov = { value: unknown; method: string; quote?: string; report_id?: number; checked?: boolean; amber?: string; source?: string };

export type Case = {
  id: number; public_id: string; incident_id: number; incident_code: string; district_id: number | null; district: string | null;
  status: string; priority: "P1" | "P2" | "P3" | "P4"; priority_reasons: string[]; priority_override: unknown;
  people_count: number | null; people_count_kind: string | null; needs: string[]; vulnerable: string[]; hazards: string[];
  lat: number | null; lng: number | null; radius_m: number | null; location_confidence: "high" | "medium" | "low" | "very_low" | null;
  location_method: string | null; location_source: string | null; location_text: string | null;
  provenance: Record<string, Prov | Prov[]>; summary: string | null; checked_by: number | null; checked_at: string | null;
  last_confirmed_at: string | null; parent_case_id: number | null; queue_since: string; flags: string[];
  attributes: Record<string, unknown>; p1_rank: number | null; version: number; created_at: string; updated_at: string;
};

export type Me = {
  user: { id: number; username: string; name: string; role: string; role_label: string };
  incidents: { id: number; code: string; name: string; status: string }[];
  districts: { id: number; name: string; incident_id: number }[];
  team: { id: number; name: string; has_app: boolean } | null;
  permissions: string[]; demo_mode: boolean; listener: string;
};

export async function listCases(params: { incident?: string; ids?: number[] }): Promise<{ cases: Case[]; seq: number }> {
  const q = new URLSearchParams();
  if (params.incident) q.set("incident", params.incident);
  if (params.ids) q.set("ids", params.ids.join(","));
  const r = await fetch(`/v1/cases?${q}`, { cache: "no-store" });
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return { cases: await r.json(), seq: Number(r.headers.get("X-Event-Seq") ?? 0) };
}
