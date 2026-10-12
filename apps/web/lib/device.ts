// The reporter's random device id (PRD F-L2 / N1). Kept in localStorage; treated like a phone number
// for duplicate matching and for the optional "Is that right?" check. Nothing personal is stored.
export function deviceId(): string {
  const key = "rakshasetu.device";
  try {
    const existing = window.localStorage.getItem(key);
    if (existing) return existing;
    const fresh = crypto.randomUUID();
    window.localStorage.setItem(key, fresh);
    return fresh;
  } catch {
    // Private mode or blocked storage: a per-tab id still works, it just isn't remembered.
    const w = window as unknown as { __rsDevice?: string };
    w.__rsDevice ??= crypto.randomUUID();
    return w.__rsDevice;
  }
}

export function newId(): string {
  return crypto.randomUUID();
}

// DEMO_MODE only (the status page checks the server says so first): after a demo reset, the demo page's QR
// hands a phone the son's synthetic device id, so the family's question can be asked of it.
export function adoptDevice(id: string): void {
  try { window.localStorage.setItem("rakshasetu.device", id); } catch { (window as unknown as { __rsDevice?: string }).__rsDevice = id; }
}
