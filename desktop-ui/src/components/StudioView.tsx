import { motion } from "framer-motion";
import {
  Check,
  CheckCircle2,
  Copy,
  FileAudio,
  FileText,
  FileVideo,
  FolderOpen,
  Play,
  Square,
  TerminalSquare,
  UploadCloud,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { chooseMedia, openManagedPath, request } from "../bridge";
import type { BackendMessage, Bootstrap, EngineId, LogLine, OutputFormat } from "../types";
import { LanguagePicker } from "./LanguagePicker";

const stages = [
  ["1", "Media input", "Validate the selected audio or video file", 0.05],
  ["2", "Audio extraction", "FFmpeg normalizes a 16 kHz mono speech stream", 0.2],
  ["3", "Model & accelerator", "Prepare the selected ASR model and device memory", 0.34],
  ["4", "ASR transcription", "Generate speech segments and word-level timestamps", 0.55],
  ["5", "Timestamp rendering", "Format the transcript into readable blocks", 0.85],
  ["6", "Save & library", "Publish the completed text into Transcripts", 1],
] as const;

function stageState(progress: number, threshold: number, index: number) {
  if (progress >= threshold || (index === 0 && progress > 0)) return "complete";
  if (progress > (stages[index - 1]?.[3] || 0)) return "active";
  return "waiting";
}

export function StudioView({
  bootstrap,
  logs,
  message,
  onBusy,
  onProgress,
  onLibraryRefresh,
  onOpenConsole,
  droppedFile,
  onClearDroppedFile,
}: {
  bootstrap: Bootstrap | null;
  logs: LogLine[];
  message: BackendMessage | null;
  onBusy: (busy: boolean) => void;
  onProgress: (value: number, message: string) => void;
  onLibraryRefresh: () => void;
  onOpenConsole: () => void;
  droppedFile?: string | null;
  onClearDroppedFile?: () => void;
}) {
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
  const [copied, setCopied] = useState(false);

  // Consume dropped file passed from window-wide drag & drop listener
  useEffect(() => {
    if (droppedFile) {
      setPickedSource(droppedFile);
      onClearDroppedFile?.();
    }
  }, [droppedFile, onClearDroppedFile]);

  const models = bootstrap?.models?.[engine] || [];
  const selectedModel = useMemo(
    () => (models.some((item) => item.id === model) ? model : models[0]?.id || ""),
    [models, model]
  );

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
    setProgress(0.01);
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
    try {
      await request("transcribe_cancel", { jobId });
    } catch (caught) {
      setError(String(caught));
    }
  };

  // Local drop area handler with HTML5 fallback
  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0] as File & { path?: string };
      if (file.path) {
        setPickedSource(file.path);
        return;
      }
    }
  };

  const copyPath = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Global keyboard shortcuts (JaneConverter Parity: Ctrl+O browse, Ctrl+Enter transcribe)
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "o") {
        e.preventDefault();
        browse();
      } else if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && source.trim() && !busy) {
        e.preventDefault();
        start();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [source, busy]);

  const fileName = source ? source.split(/[\\/]/).pop() || source : "";
  const fileExt = fileName.includes(".") ? fileName.split(".").pop()?.toUpperCase() || "" : "";
  const isVideo = ["MP4", "MKV", "WEBM", "AVI", "MOV", "FLV", "WMV"].includes(fileExt);

  const visibleLogs = logs.slice(-120);

  return (
    <section className="muted-scroll min-h-0 flex-1 overflow-y-auto p-7">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <p className="eyebrow">Local workspace</p>
          <h1 className="page-title">Transcription Studio</h1>
          <p className="page-subtitle">
            Audio and video stay on this machine. The timestamped text is published into the project&apos;s Transcripts folder.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-[var(--muted)]">
          <span className="h-2 w-2 rounded-full bg-[var(--cyan)]" />
          {bootstrap?.hardware?.accelerator || "Connecting to local engine…"}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(360px,.7fr)]">
        <div className="space-y-4">
          {/* Media Input Card (JaneConverter Parity) */}
          <section className="panel p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="section-title">Audio or video source</h2>
                <p className="hint">Drag and drop any media file from your computer or click to browse.</p>
              </div>
              {isVideo ? (
                <FileVideo size={22} className="text-[var(--accent-color,#c52b68)]" />
              ) : (
                <FileAudio size={22} className="text-[var(--accent-color,#c52b68)]" />
              )}
            </div>

            {source ? (
              /* Selected File Card with quick replace and clear buttons */
              <div className="relative rounded-2xl border border-white/10 bg-black/25 p-4 shadow-lg backdrop-blur-md">
                <div className="flex items-center gap-3.5">
                  <div className="grid size-12 shrink-0 place-items-center rounded-xl border border-white/10 bg-[var(--accent-subtle,rgba(197,43,104,0.12))] text-[var(--accent-color,#c52b68)] shadow-md">
                    {isVideo ? <FileVideo size={24} /> : <FileAudio size={24} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold text-white" title={fileName}>
                        {fileName}
                      </span>
                      {fileExt && (
                        <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-zinc-300">
                          {fileExt}
                        </span>
                      )}
                      <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                        Ready
                      </span>
                    </div>
                    <div className="mt-1 truncate font-mono text-[11px] text-zinc-400" title={source}>
                      {source}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={browse}
                      className="subtle-button flex h-9 items-center gap-1.5 px-3 text-xs font-semibold"
                      title="Choose a different media file (Ctrl+O)"
                    >
                      <FolderOpen size={14} /> Change
                    </button>
                    <button
                      type="button"
                      onClick={() => setPickedSource("")}
                      className="grid size-9 place-items-center rounded-lg border border-white/10 text-zinc-400 transition-colors hover:border-red-500/30 hover:bg-red-500/10 hover:text-red-300"
                      title="Clear selection"
                      aria-label="Clear selected file"
                    >
                      <X size={15} />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* Drop zone when no file is selected */
              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={browse}
                className={
                  "group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-all " +
                  (dragging
                    ? "scale-[1.01] border-[var(--accent-color,#c52b68)] bg-[var(--accent-subtle,rgba(197,43,104,0.12))]"
                    : "border-white/10 bg-black/20 hover:border-white/20 hover:bg-black/30")
                }
              >
                <div className="grid size-12 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-[var(--accent-color,#c52b68)] shadow-lg transition-transform group-hover:scale-110">
                  <UploadCloud size={24} className={dragging ? "animate-bounce" : ""} />
                </div>
                <div className="mt-3.5 text-sm font-medium text-white">
                  Drag & drop audio or video here, or{" "}
                  <span className="text-[var(--accent-color,#c52b68)] underline underline-offset-4">browse files</span>
                </div>
                <p className="mt-1 text-xs text-zinc-400">
                  Accepts MP3, WAV, MP4, MKV, M4A, OGG, FLAC, WEBM, and all formats supported by FFmpeg
                </p>
                <div className="mt-3.5 flex flex-wrap justify-center gap-1.5">
                  {["MP3", "WAV", "MP4", "MKV", "M4A", "OGG", "FLAC", "WEBM"].map((fmt) => (
                    <span
                      key={fmt}
                      className="rounded-md border border-white/5 bg-white/[0.03] px-2 py-0.5 font-mono text-[10px] text-zinc-400"
                    >
                      {fmt}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Transcription Settings */}
          <section className="panel p-5">
            <div className="mb-4">
              <h2 className="section-title">Transcription settings</h2>
              <p className="hint">Choose the local ASR engine that matches your accuracy, speed, and memory needs.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="field-label">ASR engine</span>
                <select
                  value={engine}
                  onChange={(event) => setEngine(event.target.value as EngineId)}
                  className="field w-full px-3 text-[12px]"
                >
                  {(bootstrap?.engines || ["whisper"]).map((item) => (
                    <option key={item} value={item}>
                      {item === "qwen3-asr"
                        ? "Qwen3-ASR (Apache-2.0)"
                        : item === "wav2vec2"
                        ? "Wav2Vec2"
                        : item === "vosk"
                        ? "Vosk / Kaldi"
                        : "Whisper"}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2">
                <span className="field-label">Model</span>
                <select
                  value={selectedModel}
                  onChange={(event) => setModel(event.target.value)}
                  className="field w-full px-3 text-[12px]"
                >
                  {models.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="mt-4 space-y-2">
              <span className="field-label">Languages</span>
              <LanguagePicker options={bootstrap?.languages || []} value={languages} onChange={setLanguages} />
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="field-label">Output format</span>
                <select
                  aria-label="Transcript output format"
                  value={outputFormat}
                  onChange={(event) => setOutputFormat(event.target.value as OutputFormat)}
                  className="field w-full px-3 text-[12px]"
                >
                  {(
                    bootstrap?.outputFormats || [
                      { id: "txt", label: "TXT · readable transcript" },
                      { id: "srt", label: "SRT · subtitles" },
                      { id: "vtt", label: "VTT · web subtitles" },
                      { id: "json", label: "JSON · segments and words" },
                    ]
                  ).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex items-end text-[10px] leading-4 text-[var(--faint)]">
                All formats are saved locally in the Transcripts folder. TXT remains the default.
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-3">
              <label className="flex items-center gap-2 text-[11px] text-[var(--muted)]">
                <input
                  type="checkbox"
                  checked={overwrite}
                  onChange={(event) => setOverwrite(event.target.checked)}
                  className="accent-[var(--accent-color,#c52b68)]"
                />{" "}
                Overwrite same-name transcript
              </label>
              <label className="flex items-center gap-2 text-[11px] text-[var(--muted)]">
                <input
                  type="checkbox"
                  checked={useCache}
                  onChange={(event) => setUseCache(event.target.checked)}
                  className="accent-[var(--cyan)]"
                />{" "}
                Use local transcript cache
              </label>
            </div>
          </section>
        </div>

        {/* Pipeline & Status Panel */}
        <section className="panel flex min-h-[386px] flex-col p-5">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="section-title">Generate transcript</h2>
              <p className="hint">The live pipeline stays visible while the model works.</p>
            </div>
            <span
              className={
                "text-[10px] font-semibold uppercase tracking-[.12em] " +
                (busy ? "text-[var(--yellow)]" : "text-[var(--green)]")
              }
            >
              {busy ? "Working" : "Ready"}
            </span>
          </div>
          <div className="progress-track mt-5 h-1.5">
            <motion.div
              className="progress-fill h-full"
              animate={{ width: Math.max(1, progress * 100) + "%" }}
              transition={{ duration: 0.25 }}
            />
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-[var(--muted)]">
            <span>{status}</span>
            <span>{Math.round(progress * 100)}%</span>
          </div>
          <div className="mt-5 space-y-2">
            {stages.map(([number, title, description, threshold], index) => {
              const state = stageState(progress, threshold, index);
              return (
                <div
                  key={number}
                  className={
                    "flex items-center gap-3 rounded-lg border px-3 py-2.5 " +
                    (state === "active"
                      ? "border-cyan-300/30 bg-cyan-300/[.05]"
                      : "border-[var(--line)] bg-black/[.1]")
                  }
                >
                  {state === "complete" ? (
                    <CheckCircle2 size={16} className="text-[var(--green)]" />
                  ) : (
                    <span
                      className={
                        "grid h-4 w-4 place-items-center rounded-full border text-[9px] " +
                        (state === "active"
                          ? "border-[var(--cyan)] text-[var(--cyan)]"
                          : "border-[var(--line-strong)] text-[var(--faint)]")
                      }
                    >
                      {number}
                    </span>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-[11px] font-semibold text-white">{title}</div>
                    <div className="mt-0.5 truncate text-[10px] text-[var(--faint)]">{description}</div>
                  </div>
                  <span
                    className={
                      "text-[9px] uppercase tracking-[.1em] " +
                      (state === "active"
                        ? "text-[var(--cyan)]"
                        : state === "complete"
                        ? "text-[var(--green)]"
                        : "text-[var(--faint)]")
                    }
                  >
                    {state}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="mt-auto flex gap-2 pt-5">
            <button
              type="button"
              disabled={!source || busy}
              className="accent-button flex h-10 flex-1 items-center justify-center gap-2 text-[11px] font-semibold"
              onClick={start}
              title="Start transcription (Ctrl+Enter)"
            >
              <Play size={14} /> Transcribe
            </button>
            <button
              type="button"
              disabled={!busy}
              className="subtle-button flex h-10 items-center gap-2 px-4 text-[11px] font-semibold"
              onClick={cancel}
            >
              <Square size={12} /> Cancel
            </button>
          </div>

          {/* Transcript Saved Card with Quick Action Buttons (JaneConverter Parity) */}
          {output && (
            <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] p-4 text-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-emerald-400">
                  <CheckCircle2 size={16} /> Transcript saved successfully
                </div>
                <button
                  type="button"
                  onClick={() => copyPath(output)}
                  className="flex items-center gap-1 text-[11px] text-emerald-300/80 transition-colors hover:text-emerald-100"
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                  {copied ? "Copied!" : "Copy path"}
                </button>
              </div>
              <div className="mt-2 break-all rounded-lg border border-emerald-500/10 bg-black/40 p-2 font-mono text-[11px] text-emerald-100/70">
                {output}
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void openManagedPath(output)}
                  className="accent-button flex h-8 items-center gap-1.5 px-3 text-[11px] font-semibold"
                >
                  <FileText size={13} /> Open transcript
                </button>
                <button
                  type="button"
                  onClick={() => void openManagedPath(bootstrap?.transcriptRoot || "")}
                  className="subtle-button flex h-8 items-center gap-1.5 px-3 text-[11px] font-semibold"
                >
                  <FolderOpen size={13} /> Open folder
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 rounded-lg border border-red-300/20 bg-red-300/[.05] p-3 text-[11px] text-[var(--red)]">
              {error}
            </div>
          )}

          {!output && (
            <button
              type="button"
              className="subtle-button mt-3 inline-flex h-9 items-center gap-2 px-3 text-[10px] font-semibold"
              onClick={() => void openManagedPath(bootstrap?.transcriptRoot || "")}
            >
              <FolderOpen size={13} /> Open Transcripts folder
            </button>
          )}
        </section>
      </div>

      {/* Live Console Output Card */}
      <section className="panel mt-4 p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="section-title">Live console</h2>
            <p className="hint">Pipeline output stays in the studio so you can see what the model is doing.</p>
          </div>
          <button
            type="button"
            className="subtle-button inline-flex h-9 shrink-0 items-center gap-2 px-3 text-[10px] font-semibold"
            onClick={onOpenConsole}
          >
            <TerminalSquare size={13} /> Open full console
          </button>
        </div>
        <div className="muted-scroll max-h-48 overflow-y-auto rounded-lg bg-[#05050b] p-3 font-mono text-[10px] leading-5">
          {visibleLogs.length === 0 ? (
            <div className="text-[var(--faint)]">JanesCriber ready. Choose a media file and press Transcribe.</div>
          ) : (
            visibleLogs.map((line) => (
              <div
                key={line.id}
                className={
                  line.tone === "error"
                    ? "text-[var(--red)]"
                    : line.tone === "warning"
                    ? "text-[var(--yellow)]"
                    : line.tone === "success"
                    ? "text-[var(--green)]"
                    : "text-[#b9c9dc]"
                }
              >
                <span className="mr-2 text-[var(--faint)]">{line.at}</span>
                {line.message}
              </div>
            ))
          )}
        </div>
      </section>
    </section>
  );
}
