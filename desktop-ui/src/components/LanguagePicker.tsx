import { AnimatePresence, motion } from "framer-motion";
import { Check, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { LanguageOption } from "../types";

export function LanguagePicker({ options, value, onChange, label = "Choose languages…" }: { options: LanguageOption[]; value: string[]; onChange: (codes: string[]) => void; label?: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState(value);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return options.filter((option) => !needle || option.name.toLowerCase().includes(needle) || option.code.toLowerCase().includes(needle));
  }, [options, query]);
  const summary = value.length === 0 ? "Auto-detect" : value.length === 1 ? options.find((item) => item.code === value[0])?.name || value[0] : value.length + " languages selected";

  const toggle = (code: string) => setDraft(draft.includes(code) ? draft.filter((item) => item !== code) : [...draft, code].slice(0, 8));

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  const modalContent = (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[9999] grid place-items-center bg-black/75 p-6 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}
        >
          <motion.section
            role="dialog"
            aria-modal="true"
            aria-labelledby="language-picker-title"
            initial={{ opacity: 0, y: 14, scale: .98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: .98 }}
            transition={{ duration: 0.16 }}
            className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-white/15 bg-[#0d0c18] shadow-2xl shadow-black/90"
          >
            <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-4 bg-white/[0.02]">
              <div>
                <h2 id="language-picker-title" className="text-sm font-semibold text-white">Language selection</h2>
                <p className="mt-1 text-[11px] text-zinc-400">Choose up to eight languages for mixed speech and code-switching.</p>
              </div>
              <button
                type="button"
                aria-label="Close language picker"
                className="subtle-button grid h-8 w-8 place-items-center rounded-lg text-zinc-400 hover:text-white"
                onClick={() => setOpen(false)}
              >
                <X size={15} />
              </button>
            </div>
            <div className="border-b border-white/[0.08] p-4 bg-black/20">
              <label className="relative block">
                <Search size={15} className="pointer-events-none absolute left-3 top-3 text-zinc-500" />
                <input
                  autoFocus
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search language, native name, or code…"
                  className="field w-full pl-9 pr-3 text-[12px] bg-black/40 border-white/10 text-white placeholder:text-zinc-500"
                />
              </label>
            </div>
            <div className="muted-scroll max-h-[390px] overflow-y-auto p-3 space-y-1 bg-[#090812]">
              {filtered.map((option) => {
                const selected = draft.includes(option.code);
                return (
                  <button
                    type="button"
                    key={option.code}
                    onClick={() => toggle(option.code)}
                    className={"flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[12px] transition-colors " + (selected ? "bg-white/[0.08] text-white" : "text-zinc-400 hover:bg-white/[0.04] hover:text-white")}
                  >
                    <span
                      className={"grid h-5 w-5 place-items-center rounded border transition-colors " + (selected ? "border-[var(--accent-color,#c52b68)] bg-[var(--accent-color,#c52b68)]/30 text-white" : "border-white/20 bg-black/40")}
                    >
                      {selected && <Check size={13} />}
                    </span>
                    <span className="flex-1 font-medium">{option.name}</span>
                    <span className="font-mono text-[10px] uppercase text-zinc-500">{option.code}</span>
                  </button>
                );
              })}
              {filtered.length === 0 && <div className="px-3 py-10 text-center text-[12px] text-zinc-500">No matching languages.</div>}
            </div>
            <div className="flex items-center justify-between border-t border-white/[0.08] px-5 py-3 bg-white/[0.02]">
              <span className="text-[11px] text-zinc-400">{draft.length}/8 selected</span>
              <button
                type="button"
                className="accent-button h-9 px-4 text-[11px] font-semibold"
                onClick={() => { onChange(draft); setOpen(false); setQuery(""); }}
              >
                Apply selection
              </button>
            </div>
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );

  return (
    <>
      <div className="flex items-center gap-2">
        <div className="field flex min-w-0 flex-1 items-center px-3 text-[12px]">{summary}</div>
        <button type="button" className="subtle-button h-10 px-3 text-[11px] font-semibold" onClick={() => { setDraft(value); setOpen(true); }}>{label}</button>
      </div>
      {typeof document !== "undefined" ? createPortal(modalContent, document.body) : modalContent}
    </>
  );
}
