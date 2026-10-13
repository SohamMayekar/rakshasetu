// Tap-to-talk recording (PRD F-L2): stops by itself after a pause once speech has started, and never runs longer
// than 30 s (Sarvam's synchronous limit). The server transcodes whatever format the browser produces, so we just
// pick one the browser supports.
//
// Made for a noisy, frightened caller:
//   - the "speech" level is set against the room's own noise (a siren, rain, a crowd), not a fixed number;
//   - a pause of 3 s ends the clip (people stop to think), and a caller who never speaks is cut off at 10 s;
//   - if the browser won't give us levels (a suspended audio context), the clip simply runs until they tap Stop
//     or 30 s, rather than being cut short by a meter that reads zero;
//   - the clip is always sent, whatever the meter thought: the server decides whether it is empty.

export type Recording = { blob: Blob; seconds: number; heardSpeech: boolean };
export type RecorderHandle = { stop: () => void };
export type MicProblem = "denied" | "none" | "busy" | "unsupported";

const TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
const PAUSE_S = 3;
const NO_SPEECH_S = 10;
const MAX_S = 30;
const CALIBRATE_S = 0.5;

export function canRecord(): boolean {
  return typeof window !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
}

/** What went wrong when the microphone could not be opened, in the three ways a person can act on. */
export function micProblem(e: unknown): MicProblem {
  const name = (e as { name?: string } | null)?.name ?? "";
  if (name === "NotAllowedError" || name === "SecurityError" || name === "PermissionDeniedError") return "denied";
  if (name === "NotFoundError" || name === "DevicesNotFoundError" || name === "OverconstrainedError") return "none";
  if (name === "NotReadableError" || name === "AbortError" || name === "TrackStartError") return "busy";
  return "unsupported";
}

export async function record(onLevel: (level: number, seconds: number) => void): Promise<{ handle: RecorderHandle; done: Promise<Recording> }> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const mimeType = TYPES.find((t) => MediaRecorder.isTypeSupported(t));
  const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks: BlobPart[] = [];

  let ctx: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  try {
    const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    ctx = new AC();
    if (ctx.state === "suspended") await ctx.resume().catch(() => {});
    if (ctx.state === "running") {
      analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);
    }
  } catch { analyser = null; }   // no meter: manual stop and the 30 s cap still work

  const buf = new Float32Array(1024);
  const started = performance.now();
  let heardSpeech = false;
  let quietSince = performance.now();
  let floor = 0, floorN = 0;
  let raf = 0;

  const stop = () => { if (rec.state !== "inactive") rec.stop(); };

  const tick = () => {
    const seconds = (performance.now() - started) / 1000;
    if (analyser) {
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (const v of buf) sum += v * v;
      const rms = Math.sqrt(sum / buf.length);
      onLevel(Math.min(1, rms * 8), seconds);
      if (seconds < CALIBRATE_S) {   // the room's own noise, before they start
        floor = (floor * floorN + rms) / (floorN + 1); floorN += 1;
      } else {
        const threshold = Math.min(0.08, Math.max(0.02, floor * 2.5));
        if (rms > threshold) { heardSpeech = true; quietSince = performance.now(); }
        const quietFor = (performance.now() - quietSince) / 1000;
        if (heardSpeech && quietFor > PAUSE_S) return stop();
        if (!heardSpeech && seconds > NO_SPEECH_S) return stop();
      }
    } else {
      onLevel(0, seconds);
    }
    if (seconds >= MAX_S) return stop();
    raf = requestAnimationFrame(tick);
  };

  const done = new Promise<Recording>((resolve) => {
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    rec.onstop = () => {
      cancelAnimationFrame(raf);
      stream.getTracks().forEach((t) => t.stop());
      ctx?.close().catch(() => {});
      resolve({ blob: new Blob(chunks, { type: rec.mimeType || "audio/webm" }), seconds: (performance.now() - started) / 1000, heardSpeech });
    };
    rec.onerror = () => stop();
  });
  rec.start(250);
  raf = requestAnimationFrame(tick);
  return { handle: { stop }, done };
}
