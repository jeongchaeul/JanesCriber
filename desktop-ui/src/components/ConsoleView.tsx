import { Trash2 } from "lucide-react";
import type { LogLine } from "../types";

export function ConsoleView({ logs, onClear }: { logs: LogLine[]; onClear: () => void }) {
  return (
    <section className="flex min-h-0 flex-1 flex-col gap-4 p-7">
      <div className="flex items-end justify-between">
        <div><p className="eyebrow">Diagnostics</p><h1 className="page-title">Console Logs</h1><p className="page-subtitle">The local engine, hardware monitor, and pipeline report here in real time.</p></div>
        <button type="button" className="subtle-button flex h-9 items-center gap-2 px-3 text-[11px]" onClick={onClear}><Trash2 size={14} /> Clear</button>
      </div>
      <div className="panel min-h-0 flex-1 overflow-hidden p-3">
        <div className="muted-scroll h-full overflow-y-auto rounded-lg bg-[#05050b] p-4 font-mono text-[11px] leading-5">
          {logs.length === 0 && <div className="text-[var(--faint)]">No messages yet. Start a job or open Hardware &amp; Pipeline to connect the local engine.</div>}
          {logs.map((line) => <div key={line.id} className={line.tone === "error" ? "text-[var(--red)]" : line.tone === "warning" ? "text-[var(--yellow)]" : line.tone === "success" ? "text-[var(--green)]" : "text-[#b9c9dc]"}><span className="mr-3 text-[var(--faint)]">{line.at}</span>{line.message}</div>)}
        </div>
      </div>
    </section>
  );
}
