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
