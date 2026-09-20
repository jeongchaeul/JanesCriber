import { motion } from "framer-motion";
import { CheckCircle2, FileAudio, FolderOpen, Play, Square, TerminalSquare, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { chooseMedia, openManagedPath, request } from "../bridge";
import type { BackendMessage, Bootstrap, EngineId, LogLine, OutputFormat } from "../types";
import { LanguagePicker } from "./LanguagePicker";

const stages = [
  ["1", "Media input", "Validate the selected audio or video file", .05],
  ["2", "Audio extraction", "FFmpeg normalizes a 16 kHz mono speech stream", .20],
  ["3", "Model & accelerator", "Prepare the selected ASR model and device memory", .34],
  ["4", "ASR transcription", "Generate speech segments and word-level timestamps", .55],
  ["5", "Timestamp rendering", "Format the transcript into readable blocks", .85],
  ["6", "Save & library", "Publish the completed text into Transcripts", 1],
] as const;

function stageState(progress: number, threshold: number, index: number) {
  if (progress >= threshold || (index === 0 && progress > 0)) return "complete";
  if (progress > (stages[index - 1]?.[3] || 0)) return "active";
  return "waiting";
}

export function StudioView({ bootstrap, logs, message, onBusy, onProgress, onLibraryRefresh, onOpenConsole }: { bootstrap: Bootstrap | null; logs: LogLine[]; message: BackendMessage | null; onBusy: (busy: boolean) => void; onProgress: (value: number, message: string) => void; onLibraryRefresh: () => void; onOpenConsole: () => void }) {
  const [source, setSource] = useState("");
  const [engine, setEngine] = useState<EngineId>("whisper");
  const [model, setModel] = useState("turbo");
  const [languages, setLanguages] = useState<string[]>([]);
  const [overwrite, setOverwrite] = useState(false);
  const [useCache, setUseCache] = useState(true);
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("txt");
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("Ready for an audio or video source.");
  const [output, setOutput] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const models = bootstrap?.models?.[engine] || [];
  const selectedModel = useMemo(() => models.some((item) => item.id === model) ? model : models[0]?.id || "", [models, model]);

  useEffect(() => {
    if (selectedModel !== model) setModel(selectedModel);
  }, [model, selectedModel]);

  useEffect(() => {
    if (!message || message.type !== "event") return;
    const eventJob = String(message.jobId || "");
    if (message.event === "job-accepted" && !jobId) setJobId(eventJob);
    if (jobId && eventJob && eventJob !== jobId) return;
    if (message.event === "progress") {
      const next = Number(message.progress || 0);
      const text = String(message.message || "Working…");
      setProgress(next);
      setStatus(text);
      onProgress(next, text);
    } else if (message.event === "completed") {
      const path = String(message.output || "");
      setProgress(1);
      setStatus("Transcript generated successfully.");
      setOutput(path);
      setBusy(false);
      setJobId(null);
      onBusy(false);
      onProgress(1, "Transcript generated successfully.");
      onLibraryRefresh();
    } else if (message.event === "cancelled") {
      setStatus("Transcription cancelled.");
      setBusy(false);
      setJobId(null);
      onBusy(false);
    } else if (message.event === "error") {
      const text = String(message.message || "The transcription worker failed.");
      setError(text);
      setStatus("Could not complete the transcription.");
      setBusy(false);
      setJobId(null);
      onBusy(false);
    }
  }, [message, jobId, onBusy, onLibraryRefresh, onProgress]);

  const setPickedSource = (path: string) => {
    setSource(path);
    setOutput(null);
    setError(null);
    setStatus("Ready to transcribe.");
  };

  const browse = async () => {
    try {
      const path = await chooseMedia();
      if (path) setPickedSource(path);
    } catch (caught) {
      setError(String(caught));
    }
  };

  const start = async () => {
    if (!source.trim() || busy) return;
    setError(null);
    setOutput(null);
    setBusy(true);
    setProgress(.01);
    setStatus("Starting the local transcription worker…");
    onBusy(true);
    try {
      const result = await request<{ jobId: string }>("transcribe_start", {
        source,
        engine,
        model: selectedModel,
        languages,
        overwrite,
        useCache,
        outputFormat,
      });
      setJobId(result.jobId);
    } catch (caught) {
      const text = String(caught);
      setError(text);
      setStatus("The local engine could not start.");
      setBusy(false);
      onBusy(false);
    }
  };

  const cancel = async () => {
    if (!jobId) return;
    setStatus("Cancellation requested…");
    try { await request("transcribe_cancel", { jobId }); } catch (caught) { setError(String(caught)); }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0] as (File & { path?: string }) | undefined;
    if (file?.path) setPickedSource(file.path);
    else if (file?.name) setError("The dropped item did not expose a local path. Use Browse for this file.");
  };

  const visibleLogs = logs.slice(-120);

  return (
    <section className="muted-scroll min-h-0 flex-1 overflow-y-auto p-7">
      <div className="mb-6 flex items-end justify-between">
        <div><p className="eyebrow">Local workspace</p><h1 className="page-title">Transcription Studio</h1><p className="page-subtitle">Audio and video stay on this machine. The timestamped text is published into the project&apos;s Transcripts folder.</p></div>
        <div className="flex items-center gap-2 text-[11px] text-[var(--muted)]"><span className="h-2 w-2 rounded-full bg-[var(--cyan)]" />{bootstrap?.hardware?.accelerator || "Connecting to local engine…"}</div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(360px,.7fr)]">
        <div className="space-y-4">
          <section className="panel p-5">
            <div className="mb-4 flex items-center justify-between"><div><h2 className="section-title">Choose audio or video</h2><p className="hint">Every format FFmpeg can read is accepted. Drop a file below or browse for a local path.</p></div><FileAudio size={21} className="text-[var(--cyan)]/80" /></div>
            <div onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={handleDrop} className={"rounded-xl border border-dashed p-4 transition-colors " + (dragging ? "border-[var(--cyan)] bg-cyan-300/[.07]" : "border-[var(--line-strong)] bg-black/[.12]")}>
              <div className="flex items-center gap-3">
                <UploadCloud size={19} className={dragging ? "text-[var(--cyan)]" : "text-[var(--faint)]"} />
                <input aria-label="Selected media path" value={source} onChange={(event) => setPickedSource(event.target.value)} placeholder="Drop a file here or enter a path…" className="field h-10 min-w-0 flex-1 px-3 text-[12px]" />
                <button type="button" className="subtle-button flex h-10 items-center gap-2 px-4 text-[11px] font-semibold" onClick={browse}><FolderOpen size={14} /> Browse</button>
              </div>
              <p className="mt-3 text-[10px] text-[var(--faint)]">The source file is never moved or modified.</p>
            </div>
          </section>

          <section className="panel p-5">
            <div className="mb-4"><h2 className="section-title">Transcription settings</h2><p className="hint">Choose the local ASR engine that matches your accuracy, speed, and memory needs.</p></div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2"><span className="field-label">ASR engine</span><select value={engine} onChange={(event) => setEngine(event.target.value as EngineId)} className="field w-full px-3 text-[12px]">{(bootstrap?.engines || ["whisper"]).map((item) => <option key={item} value={item}>{item === "qwen3-asr" ? "Qwen3-ASR (Apache-2.0)" : item === "wav2vec2" ? "Wav2Vec2" : item === "vosk" ? "Vosk / Kaldi" : "Whisper"}</option>)}</select></label>
              <label className="space-y-2"><span className="field-label">Model</span><select value={selectedModel} onChange={(event) => setModel(event.target.value)} className="field w-full px-3 text-[12px]">{models.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
            </div>
            <div className="mt-4 space-y-2"><span className="field-label">Languages</span><LanguagePicker options={bootstrap?.languages || []} value={languages} onChange={setLanguages} /></div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="space-y-2"><span className="field-label">Output format</span><select aria-label="Transcript output format" value={outputFormat} onChange={(event) => setOutputFormat(event.target.value as OutputFormat)} className="field w-full px-3 text-[12px]"><option value="txt">TXT · readable transcript</option><option value="srt">SRT · subtitles</option><option value="vtt">VTT · web subtitles</option><option value="json">JSON · segments and words</option></select></label><div className="flex items-end text-[10px] leading-4 text-[var(--faint)]">All formats are saved locally in the Transcripts folder. TXT remains the default.</div></div>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-3">
              <label className="flex items-center gap-2 text-[11px] text-[var(--muted)]"><input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} className="accent-[var(--pink)]" /> Overwrite same-name transcript</label>
              <label className="flex items-center gap-2 text-[11px] text-[var(--muted)]"><input type="checkbox" checked={useCache} onChange={(event) => setUseCache(event.target.checked)} className="accent-[var(--cyan)]" /> Use local transcript cache</label>
            </div>
          </section>
        </div>

        <section className="panel flex min-h-[386px] flex-col p-5">
          <div className="flex items-start justify-between"><div><h2 className="section-title">Generate transcript</h2><p className="hint">The live pipeline stays visible while the model works.</p></div><span className={"text-[10px] font-semibold uppercase tracking-[.12em] " + (busy ? "text-[var(--yellow)]" : "text-[var(--green)]")}>{busy ? "Working" : "Ready"}</span></div>
          <div className="mt-5 progress-track h-1.5"><motion.div className="progress-fill h-full" animate={{ width: Math.max(1, progress * 100) + "%" }} transition={{ duration: .25 }} /></div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-[var(--muted)]"><span>{status}</span><span>{Math.round(progress * 100)}%</span></div>
          <div className="mt-5 space-y-2">
            {stages.map(([number, title, description, threshold], index) => {
              const state = stageState(progress, threshold, index);
              return <div key={number} className={"flex items-center gap-3 rounded-lg border px-3 py-2.5 " + (state === "active" ? "border-cyan-300/30 bg-cyan-300/[.05]" : "border-[var(--line)] bg-black/[.1]")}>
                {state === "complete" ? <CheckCircle2 size={16} className="text-[var(--green)]" /> : <span className={"grid h-4 w-4 place-items-center rounded-full border text-[9px] " + (state === "active" ? "border-[var(--cyan)] text-[var(--cyan)]" : "border-[var(--line-strong)] text-[var(--faint)]")}>{number}</span>}
                <div className="min-w-0 flex-1"><div className="text-[11px] font-semibold text-white">{title}</div><div className="mt-0.5 truncate text-[10px] text-[var(--faint)]">{description}</div></div>
                <span className={"text-[9px] uppercase tracking-[.1em] " + (state === "active" ? "text-[var(--cyan)]" : state === "complete" ? "text-[var(--green)]" : "text-[var(--faint)]")}>{state}</span>
              </div>;
            })}
          </div>
          <div className="mt-auto flex gap-2 pt-5"><button type="button" disabled={!source || busy} className="accent-button flex h-10 flex-1 items-center justify-center gap-2 text-[11px] font-semibold" onClick={start}><Play size={14} /> Transcribe</button><button type="button" disabled={!busy} className="subtle-button flex h-10 items-center gap-2 px-4 text-[11px] font-semibold" onClick={cancel}><Square size={12} /> Cancel</button></div>
          {output && <div className="mt-4 rounded-lg border border-emerald-300/20 bg-emerald-300/[.05] p-3 text-[11px] text-[var(--green)]"><div className="font-semibold">Transcript saved</div><div className="mt-1 break-all font-mono text-[10px] text-emerald-100/70">{output}</div></div>}
          {error && <div className="mt-4 rounded-lg border border-red-300/20 bg-red-300/[.05] p-3 text-[11px] text-[var(--red)]">{error}</div>}
          <button type="button" className="subtle-button mt-3 inline-flex h-9 items-center gap-2 px-3 text-[10px] font-semibold" onClick={() => void openManagedPath(bootstrap?.transcriptRoot || "")}><FolderOpen size={13} /> Open Transcripts folder</button>
        </section>
      </div>

      <section className="panel mt-4 p-5">
        <div className="mb-3 flex items-center justify-between gap-3"><div><h2 className="section-title">Live console</h2><p className="hint">Pipeline output stays in the studio so you can see what the model is doing.</p></div><button type="button" className="subtle-button inline-flex h-9 shrink-0 items-center gap-2 px-3 text-[10px] font-semibold" onClick={onOpenConsole}><TerminalSquare size={13} /> Open full console</button></div>
        <div className="muted-scroll max-h-48 overflow-y-auto rounded-lg bg-[#05050b] p-3 font-mono text-[10px] leading-5">
          {visibleLogs.length === 0 ? <div className="text-[var(--faint)]">JanesCriber ready. Choose a media file and press Transcribe.</div> : visibleLogs.map((line) => <div key={line.id} className={line.tone === "error" ? "text-[var(--red)]" : line.tone === "warning" ? "text-[var(--yellow)]" : line.tone === "success" ? "text-[var(--green)]" : "text-[#b9c9dc]"}><span className="mr-2 text-[var(--faint)]">{line.at}</span>{line.message}</div>)}
        </div>
      </section>
    </section>
  );
}
