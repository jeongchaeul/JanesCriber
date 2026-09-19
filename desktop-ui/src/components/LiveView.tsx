import { AlertTriangle, Mic, RefreshCw, Square, Wifi } from "lucide-react";
import { useEffect, useState } from "react";
import { request } from "../bridge";
import type { BackendMessage, Bootstrap, CaptureSource, EngineId } from "../types";
import { LanguagePicker } from "./LanguagePicker";

export function LiveView({ bootstrap, message, visible, onLibraryRefresh, onLiveState }: { bootstrap: Bootstrap | null; message: BackendMessage | null; visible: boolean; onLibraryRefresh: () => void; onLiveState: (active: boolean) => void }) {
  const [mode, setMode] = useState<"microphone" | "system" | "application">("microphone");
  const [sources, setSources] = useState<CaptureSource[]>([]);
  const [selectedSource, setSelectedSource] = useState<CaptureSource | null>(null);
  const [engine, setEngine] = useState<EngineId>("whisper");
  const [model, setModel] = useState("tiny");
  const [languages, setLanguages] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [active, setActive] = useState(false);
  const [status, setStatus] = useState("Ready for an audio source.");
  const [text, setText] = useState("Live notes will appear here as speech is detected.");
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const models = bootstrap?.models?.[engine] || [];
  useEffect(() => {
    const next = models.find((item) => item.id === model)?.id || models[0]?.id || "";
    if (next !== model) setModel(next);
  }, [engine, models, model]);

  const refreshSources = async () => {
    try {
      const next = await request<CaptureSource[]>("live_sources", { mode });
      setSources(next);
      setSelectedSource((current) => next.find((source) => source.identifier === current?.identifier) || next[0] || null);
      setError(null);
    } catch (caught) { setError(String(caught)); }
  };

  useEffect(() => { if (visible) void refreshSources(); }, [mode, visible]);

  useEffect(() => {
    if (!message || message.type !== "event") return;
    if (sessionId && message.sessionId && message.sessionId !== sessionId) return;
    if (message.event === "live-status") setStatus(String(message.message || "Listening…"));
    if (message.event === "live-text") setText(String(message.text || ""));
    if (message.event === "live-finished") {
      setOutput(String(message.output || ""));
      setStatus("Live transcription saved.");
      setActive(false);
      setSessionId(null);
      onLiveState(false);
      onLibraryRefresh();
    }
    if (message.event === "live-error") {
      setError(String(message.message || "The live worker failed."));
      setActive(false);
      setSessionId(null);
      onLiveState(false);
    }
  }, [message, sessionId, onLibraryRefresh, onLiveState]);

  const start = async () => {
    if (active || !selectedSource) return;
    setError(null);
    setOutput(null);
    setText("Starting the live worker…");
    try {
      const result = await request<{ sessionId: string }>("live_start", { mode, source: selectedSource, engine, model, languages });
      setSessionId(result.sessionId);
      setActive(true);
      onLiveState(true);
      setStatus("Listening…");
    } catch (caught) { setError(String(caught)); }
  };

  const stop = async () => {
    if (!sessionId) return;
    setStatus("Stopping and saving the live transcript…");
    try { await request("live_stop", { sessionId }); } catch (caught) { setError(String(caught)); }
  };

  return (
    <section className="muted-scroll min-h-0 flex-1 overflow-y-auto p-7">
      <div className="mb-6 flex items-end justify-between"><div><p className="eyebrow">Accessibility capture</p><h1 className="page-title">Live Transcription</h1><p className="page-subtitle">Choose a microphone, system output, or visible application and turn speech into timestamped documentation while it happens.</p></div><div className={"flex items-center gap-2 text-[11px] " + (active ? "text-[var(--green)]" : "text-[var(--muted)]")}><span className={"h-2 w-2 rounded-full " + (active ? "bg-[var(--green)] animate-pulse" : "bg-[var(--faint)]")} />{active ? "LISTENING" : "IDLE"}</div></div>
      <section className="panel p-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2"><span className="field-label">Capture mode</span><select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)} disabled={active} className="field w-full px-3 text-[12px]"><option value="microphone">Microphone</option><option value="system">System output</option><option value="application">Application output</option></select></label>
          <label className="space-y-2"><span className="field-label">Capture source</span><div className="flex gap-2"><select value={selectedSource?.identifier || ""} onChange={(event) => setSelectedSource(sources.find((item) => item.identifier === event.target.value) || null)} disabled={active} className="field min-w-0 flex-1 px-3 text-[11px]"><option value="">Choose a source…</option>{sources.map((source) => <option key={source.identifier || source.label} value={source.identifier || ""}>{source.label}</option>)}</select><button type="button" aria-label="Refresh capture sources" className="subtle-button grid h-10 w-10 place-items-center" onClick={() => void refreshSources()}><RefreshCw size={14} /></button></div></label>
          <label className="space-y-2"><span className="field-label">ASR engine</span><select value={engine} onChange={(event) => setEngine(event.target.value as EngineId)} disabled={active} className="field w-full px-3 text-[12px]">{(bootstrap?.engines || ["whisper"]).filter((item) => item !== "qwen3-asr").map((item) => <option key={item} value={item}>{item === "wav2vec2" ? "Wav2Vec2" : item === "vosk" ? "Vosk / Kaldi" : "Whisper"}</option>)}</select></label>
          <label className="space-y-2"><span className="field-label">Model</span><select value={model} onChange={(event) => setModel(event.target.value)} disabled={active} className="field w-full px-3 text-[12px]">{models.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        </div>
        <div className="mt-4 space-y-2"><span className="field-label">Languages</span><LanguagePicker options={bootstrap?.languages || []} value={languages} onChange={setLanguages} label="Choose languages…" /></div>
        <div className="mt-4 flex items-start gap-3 rounded-lg border border-yellow-300/20 bg-yellow-300/[.05] p-3 text-[11px] leading-5 text-[var(--yellow)]"><AlertTriangle size={16} className="mt-0.5 shrink-0" /><span>For long sessions, Tiny or Base is recommended. Small, Turbo, and larger models use substantially more RAM. Application and system capture may also require Windows audio permissions.</span></div>
        <div className="mt-5 flex items-center gap-2"><button type="button" disabled={active || !selectedSource} className="accent-button flex h-10 items-center gap-2 px-5 text-[11px] font-semibold" onClick={() => void start()}><Mic size={14} /> Start listening</button><button type="button" disabled={!active} className="subtle-button flex h-10 items-center gap-2 px-5 text-[11px] font-semibold" onClick={() => void stop()}><Square size={12} /> Stop &amp; save</button><span className="ml-auto text-[11px] text-[var(--muted)]">{status}</span></div>
      </section>
      <section className="panel mt-4 flex min-h-[430px] flex-col p-5"><div className="mb-3 flex items-center justify-between"><div><h2 className="section-title">Live Notes</h2><p className="hint">The transcript is continuously saved into the local Transcripts folder.</p></div><Wifi size={18} className={active ? "text-[var(--green)]" : "text-[var(--faint)]"} /></div><div className="muted-scroll min-h-0 flex-1 overflow-y-auto rounded-lg bg-[#05050b] p-4 font-mono text-[11px] leading-6 text-[#d6d9e5] whitespace-pre-wrap">{text}</div>{output && <div className="mt-3 break-all text-[10px] text-[var(--green)]">Saved: {output}</div>}{error && <div className="mt-3 rounded-lg border border-red-300/20 bg-red-300/[.05] p-3 text-[11px] text-[var(--red)]">{error}</div>}</section>
    </section>
  );
}
