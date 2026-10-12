// Tap-to-talk recording (PRD F-L2): stops by itself after ~2 s of silence once speech has started,
// and never runs longer than 30 s (Sarvam's synchronous limit). The server transcodes whatever format
// the browser produces, so we just pick one the browser supports.

export type Recording = { blob: Blob; seconds: number };
export type RecorderHandle = { stop: () => void };

const TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

export function canRecord(): boolean {
  return typeof window !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
}

export async function record(onLevel: (level: number, seconds: number) => void): Promise<{ handle: RecorderHandle; done: Promise<Recording> }> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  const mimeType = TYPES.find((t) => MediaRecorder.isTypeSupported(t));
  const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks: BlobPart[] = [];
  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const buf = new Float32Array(analyser.fftSize);
  const started = performance.now();
  let heardSpeech = false;
  let quietSince = performance.now();
  let raf = 0;

  const stop = () => {
    if (rec.state !== "inactive") rec.stop();
  };
  const tick = () => {
    analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (const v of buf) sum += v * v;
    const rms = Math.sqrt(sum / buf.length);
    const seconds = (performance.now() - started) / 1000;
    onLevel(Math.min(1, rms * 8), seconds);
    if (rms > 0.02) {
      heardSpeech = true;
      quietSince = performance.now();
    }
    const quietFor = (performance.now() - quietSince) / 1000;
    if ((heardSpeech && quietFor > 2) || seconds >= 30) stop();
    else raf = requestAnimationFrame(tick);
  };

  const done = new Promise<Recording>((resolve) => {
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      cancelAnimationFrame(raf);
      stream.getTracks().forEach((t) => t.stop());
      ctx.close().catch(() => {});
      resolve({ blob: new Blob(chunks, { type: rec.mimeType || "audio/webm" }), seconds: (performance.now() - started) / 1000 });
    };
  });
  rec.start(250);
  raf = requestAnimationFrame(tick);
  return { handle: { stop }, done };
}
