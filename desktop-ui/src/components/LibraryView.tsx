import { motion } from "framer-motion";
import { FileText, FolderOpen, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { openManagedPath, request } from "../bridge";
import type { Bootstrap, TranscriptEntry } from "../types";

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function formatDate(value: number): string {
  try { return new Date(value * 1000).toLocaleString(); } catch { return "Unknown date"; }
}

export function LibraryView({ bootstrap, refreshKey }: { bootstrap: Bootstrap | null; refreshKey: number }) {
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [selected, setSelected] = useState<TranscriptEntry | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const next = await request<TranscriptEntry[]>("library_list");
      setEntries(next);
      if (selected) {
        const stillThere = next.find((entry) => entry.path === selected.path);
        if (!stillThere) { setSelected(null); setContent(""); }
      }
      setError(null);
    } catch (caught) { setError(String(caught)); }
    finally { setLoading(false); }
  };

  useEffect(() => { void refresh(); }, [refreshKey]);

  const select = async (entry: TranscriptEntry) => {
    setSelected(entry);
    try {
      const result = await request<{ content: string }>("library_read", { path: entry.path });
      setContent(result.content);
      setError(null);
    } catch (caught) { setError(String(caught)); }
  };

  const remove = async (entry: TranscriptEntry) => {
    if (!window.confirm("Delete " + entry.name + " from the Transcripts folder?")) return;
    try {
      await request("library_delete", { path: entry.path });
      if (selected?.path === entry.path) { setSelected(null); setContent(""); }
      await refresh();
    } catch (caught) { setError(String(caught)); }
  };

  const renderLine = (line: string, index: number) => {
    const timestamp = /^\[[0-9:.]+ --> [0-9:.]+\]$/.test(line.trim());
    const quote = line.startsWith(">");
    if (timestamp) return <div key={index} className="mt-4 font-mono text-[11px] font-semibold text-[var(--pink)] first:mt-0">{line}</div>;
    if (quote) return <div key={index} className="mt-1 border-l border-[var(--pink)]/35 pl-3 text-[13px] leading-6 text-[#d9d6e2]">{line.slice(1).replace(/^ /, "")}</div>;
    if (!line.trim()) return <div key={index} className="h-2" />;
    return <div key={index} className="text-[11px] leading-5 text-[var(--faint)]">{line}</div>;
  };

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden p-7">
      <div className="mb-6 flex shrink-0 items-end justify-between"><div><p className="eyebrow">Project files</p><h1 className="page-title">Transcript Library</h1><p className="page-subtitle">Read, manage, and open the timestamped text generated in the local Transcripts folder.</p></div><div className="flex gap-2"><button type="button" className="subtle-button flex h-9 items-center gap-2 px-3 text-[11px]" onClick={() => void refresh()}><RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh</button><button type="button" className="subtle-button flex h-9 items-center gap-2 px-3 text-[11px]" onClick={() => void openManagedPath(bootstrap?.transcriptRoot || "")}><FolderOpen size={14} /> Open folder</button></div></div>
      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[330px_minmax(0,1fr)] xl:grid-rows-1">
        <section className="panel flex min-h-0 flex-col overflow-hidden p-3">
          <div className="shrink-0 border-b border-[var(--line)] px-2 pb-3 text-[11px] font-semibold uppercase tracking-[.12em] text-[var(--muted)]">{entries.length} transcript{entries.length === 1 ? "" : "s"}</div>
          <div className="muted-scroll min-h-0 flex-1 overflow-y-auto pt-2">
            {entries.map((entry) => <motion.div layout key={entry.path} className={"group mb-1 flex items-center gap-2 rounded-lg border px-2 py-2.5 " + (selected?.path === entry.path ? "border-[var(--pink)]/35 bg-[var(--pink-soft)]" : "border-transparent hover:border-[var(--line)] hover:bg-white/[.03]")}>
              <button type="button" onClick={() => void select(entry)} className="flex min-w-0 flex-1 items-center gap-2 text-left"><FileText size={16} className={selected?.path === entry.path ? "text-[var(--pink)]" : "text-[var(--faint)]"} /><span className="min-w-0"><span className="block truncate text-[11px] text-white">{entry.name}</span><span className="mt-1 block text-[9px] text-[var(--faint)]">{formatSize(entry.size)} · {formatDate(entry.modified)}</span></span></button>
              <button type="button" aria-label={"Delete " + entry.name} onClick={() => void remove(entry)} className="grid h-7 w-7 shrink-0 place-items-center rounded text-[var(--faint)] opacity-0 transition-opacity hover:bg-red-300/10 hover:text-[var(--red)] group-hover:opacity-100"><Trash2 size={13} /></button>
            </motion.div>)}
            {entries.length === 0 && <div className="px-3 py-12 text-center text-[11px] leading-5 text-[var(--faint)]">No transcripts yet.<br />Generate one in Transcription Studio.</div>}
          </div>
        </section>
        <section className="panel flex min-h-0 flex-col overflow-hidden p-5">
          <div className="flex items-center justify-between border-b border-[var(--line)] pb-4"><div><h2 className="section-title">Transcript viewer</h2><p className="hint">{selected ? selected.name : "Select a transcript to read it without opening Windows Explorer."}</p></div>{selected && <button type="button" className="subtle-button flex h-8 items-center gap-2 px-3 text-[10px]" onClick={() => void openManagedPath(selected.path)}><FolderOpen size={13} /> Open file</button>}</div>
          <div className="muted-scroll min-h-0 flex-1 overflow-y-auto pt-5">
            {selected ? <div className="max-w-3xl">{content.split(/\r?\n/).map(renderLine)}</div> : <div className="grid h-full min-h-[300px] place-items-center text-center text-[11px] text-[var(--faint)]"><div><FileText size={30} className="mx-auto mb-3 text-[var(--faint)]" /><div>Your selected transcript will appear here.</div></div></div>}
          </div>
          {error && <div className="mt-4 rounded-lg border border-red-300/20 bg-red-300/[.05] p-3 text-[11px] text-[var(--red)]">{error}</div>}
        </section>
      </div>
    </section>
  );
}
