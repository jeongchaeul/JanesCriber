import { Activity, Cpu, HardDrive, MemoryStick, MonitorCog, Thermometer } from "lucide-react";
import { useEffect, useState } from "react";
import { request } from "../bridge";
import type { Bootstrap, HardwareSnapshot } from "../types";

function Meter({ label, value, detail, color = "cyan" }: { label: string; value: number; detail: string; color?: "cyan" | "pink" | "green" }) {
  const fill = color === "pink" ? "bg-[var(--pink)]" : color === "green" ? "bg-[var(--green)]" : "bg-[var(--cyan)]";
  return <div><div className="mb-1 flex items-center justify-between text-[10px]"><span className="text-[var(--muted)]">{label}</span><span className="font-mono text-[var(--faint)]">{detail}</span></div><div className="progress-track h-1.5"><div className={"h-full rounded-full transition-[width] duration-500 " + fill} style={{ width: Math.max(0, Math.min(100, value)) + "%" }} /></div></div>;
}

export function HardwareView({ bootstrap, active, visible, progress, progressMessage }: { bootstrap: Bootstrap | null; active: boolean; visible: boolean; progress: number; progressMessage: string }) {
  const [snapshot, setSnapshot] = useState<HardwareSnapshot | null>(null);

  useEffect(() => {
    if (!visible) return;
    let mounted = true;
    const sample = async () => {
      try { const next = await request<HardwareSnapshot>("hardware_snapshot", { active }); if (mounted) setSnapshot(next); } catch { /* console view receives bridge failures */ }
    };
    void sample();
    const timer = window.setInterval(() => void sample(), 1800);
    return () => { mounted = false; window.clearInterval(timer); };
  }, [active, visible]);

  const info = bootstrap?.hardware || {};
  const current = snapshot;
  const stages = [
    ["1", "Media input", .05],
    ["2", "Audio extraction", .20],
    ["3", "Model & accelerator", .34],
    ["4", "ASR transcription", .55],
    ["5", "Timestamp rendering", .85],
    ["6", "Save & library", 1],
  ] as const;

  return (
    <section className="muted-scroll min-h-0 flex-1 overflow-y-auto p-7">
      <div className="mb-6"><p className="eyebrow">System insight</p><h1 className="page-title">Hardware &amp; Pipeline</h1><p className="page-subtitle">Live telemetry and the same six-stage pipeline contract used by the legacy launcher.</p></div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,.85fr)_minmax(0,1.15fr)]">
        <section className="panel p-5"><div className="mb-5 flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-lg border border-cyan-300/20 bg-cyan-300/[.06] text-[var(--cyan)]"><MonitorCog size={19} /></div><div><h2 className="section-title">Detected hardware</h2><p className="hint">Friendly names are read from the operating system.</p></div></div><div className="space-y-4"><div className="rounded-lg border border-[var(--line)] bg-black/[.12] p-3"><div className="field-label">Processor</div><div className="mt-1 text-[13px] text-white">{String(info.cpu || "Detecting…")}</div><div className="mt-1 text-[10px] text-[var(--faint)]">{String(info.cores || "—")} logical cores</div></div><div className="rounded-lg border border-[var(--line)] bg-black/[.12] p-3"><div className="field-label">Accelerator</div><div className="mt-1 text-[13px] text-white">{current?.gpuBackend || String(info.accelerator || "Detecting…")}</div><div className="mt-1 text-[10px] text-[var(--faint)]">{current?.gpuName || String(info.gpu || "No dedicated GPU detected")} · Torch {String(info.torch_version || "—")}</div></div><div className="rounded-lg border border-[var(--line)] bg-black/[.12] p-3"><div className="field-label">Runtime paths</div><div className="mt-2 break-all font-mono text-[10px] leading-5 text-[var(--muted)]">Transcripts: {bootstrap?.transcriptRoot || "—"}<br />Cache: {bootstrap?.cacheRoot || "—"}<br />Scratch: {bootstrap?.tempRoot || "—"}</div></div></div></section>
        <section className="panel p-5"><div className="mb-5 flex items-center justify-between"><div><h2 className="section-title">Live hardware monitor</h2><p className="hint">Values refresh while idle and include worker usage during a job.</p></div><div className={"flex items-center gap-2 text-[10px] uppercase tracking-[.1em] " + (active ? "text-[var(--yellow)]" : "text-[var(--green)]")}><span className="h-1.5 w-1.5 rounded-full bg-current" />{active ? "Transcription active" : "Monitoring idle system"}</div></div><div className="grid gap-5 sm:grid-cols-2"><div className="space-y-4"><Meter label="System CPU" value={current?.cpuSystemPct || 0} detail={(current?.cpuSystemPct || 0).toFixed(1) + "%"} /><Meter label="JanesCriber CPU" value={current?.cpuAppPct || 0} detail={(current?.cpuAppPct || 0).toFixed(1) + "%"} color="pink" /><Meter label="System RAM" value={current?.ramSystemPct || 0} detail={(current?.ramUsedGb || 0).toFixed(1) + " / " + (current?.ramTotalGb || 0).toFixed(1) + " GB"} /></div><div className="space-y-4"><Meter label="GPU utilization" value={current?.gpuSystemPct || 0} detail={(current?.gpuSystemPct || 0).toFixed(1) + "%"} color="green" /><Meter label="VRAM" value={current?.gpuVramTotalMb ? current.gpuVramUsedMb / current.gpuVramTotalMb * 100 : 0} detail={(current?.gpuVramUsedMb || 0) + " / " + (current?.gpuVramTotalMb || 0) + " MB"} /><div className="flex items-center gap-2 text-[10px] text-[var(--muted)]"><Thermometer size={13} /> GPU temperature: {current?.gpuTempC || 0}°C · source: {current?.telemetrySource || "unavailable"}</div></div></div></section>
      </div>
      <section className="panel mt-4 p-5"><div className="mb-4 flex items-end justify-between"><div><h2 className="section-title">Transcription pipeline tracker</h2><p className="hint">{active ? progressMessage : "Waiting for a transcription request."}</p></div><div className="font-mono text-[11px] text-[var(--yellow)]">{Math.round(progress * 100).toString().padStart(3, "0")}%</div></div><div className="space-y-2">{stages.map(([number, label, threshold], index) => { const complete = active && progress >= threshold || (!active && progress === 1 && threshold === 1); const currentStage = active && progress > (stages[index - 1]?.[2] || 0) && progress < threshold; return <div key={number} className={"flex items-center gap-3 rounded-lg border px-3 py-3 " + (currentStage ? "border-cyan-300/30 bg-cyan-300/[.05]" : "border-[var(--line)] bg-black/[.12]")}><span className={"grid h-5 w-5 place-items-center rounded-full border text-[9px] " + (complete ? "border-[var(--green)] text-[var(--green)]" : currentStage ? "border-[var(--cyan)] text-[var(--cyan)]" : "border-[var(--line-strong)] text-[var(--faint)]")}>{complete ? "✓" : number}</span><div className="min-w-0 flex-1"><div className="text-[11px] font-semibold text-white">{label}</div><div className="mt-0.5 text-[10px] text-[var(--faint)]">{index === 0 ? "Validate the selected audio or video file" : index === 1 ? "FFmpeg normalizes a 16 kHz mono speech stream" : index === 2 ? "Prepare the model and move it into accelerator memory" : index === 3 ? "Generate speech segments and word-level timestamps" : index === 4 ? "Format readable timestamp blocks" : "Publish safely into the Transcripts folder"}</div></div><span className={"text-[9px] uppercase tracking-[.1em] " + (complete ? "text-[var(--green)]" : currentStage ? "text-[var(--cyan)]" : "text-[var(--faint)]")}>{complete ? "Complete" : currentStage ? "Active" : "Waiting"}</span></div>; })}</div></section>
      <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="panel-raised flex items-center gap-3 p-4"><Cpu size={17} className="text-[var(--cyan)]" /><span className="text-[11px] text-[var(--muted)]">CPU app memory <strong className="ml-1 text-white">{(current?.ramAppMb || 0).toFixed(0)} MB</strong></span></div><div className="panel-raised flex items-center gap-3 p-4"><MemoryStick size={17} className="text-[var(--pink)]" /><span className="text-[11px] text-[var(--muted)]">App VRAM <strong className="ml-1 text-white">{current?.gpuAppVramMb || 0} MB</strong></span></div><div className="panel-raised flex items-center gap-3 p-4"><Activity size={17} className="text-[var(--green)]" /><span className="text-[11px] text-[var(--muted)]">Telemetry <strong className="ml-1 text-white">{current?.telemetrySource || "pending"}</strong></span></div></div>
    </section>
  );
}
