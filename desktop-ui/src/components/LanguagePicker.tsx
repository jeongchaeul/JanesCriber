import { AnimatePresence, motion } from "framer-motion";
import { Check, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
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

  return (
    <>
      <div className="flex items-center gap-2">
        <div className="field flex min-w-0 flex-1 items-center px-3 text-[12px]">{summary}</div>
        <button type="button" className="subtle-button h-10 px-3 text-[11px] font-semibold" onClick={() => { setDraft(value); setOpen(true); }}>{label}</button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
            <motion.section role="dialog" aria-modal="true" aria-labelledby="language-picker-title" initial={{ opacity: 0, y: 12, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8 }} className="panel w-full max-w-xl overflow-hidden shadow-2xl shadow-black/40">
              <div className="flex items-center justify-between border-b border-[var(--line)] px-5 py-4">
                <div>
                  <h2 id="language-picker-title" className="text-sm font-semibold text-white">Language selection</h2>
                  <p className="mt-1 text-[11px] text-[var(--muted)]">Choose up to eight languages for mixed speech and code-switching.</p>
                </div>
                <button type="button" aria-label="Close language picker" className="subtle-button grid h-8 w-8 place-items-center" onClick={() => setOpen(false)}><X size={15} /></button>
              </div>
              <div className="border-b border-[var(--line)] p-4">
                <label className="relative block">
                  <Search size={15} className="pointer-events-none absolute left-3 top-3 text-[var(--faint)]" />
                  <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search language, native name, or code…" className="field w-full pl-9 pr-3 text-[12px]" />
                </label>
              </div>
              <div className="muted-scroll max-h-[390px] overflow-y-auto p-3">
                {filtered.map((option) => {
                  const selected = draft.includes(option.code);
                  return (
                    <button type="button" key={option.code} onClick={() => toggle(option.code)} className={"flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[12px] transition-colors " + (selected ? "bg-[var(--pink-soft)] text-white" : "text-[var(--muted)] hover:bg-white/[.04] hover:text-white")}>
                      <span className={"grid h-5 w-5 place-items-center rounded border " + (selected ? "border-[var(--pink)] bg-[var(--pink)]/25 text-[#f0a6c4]" : "border-[var(--line-strong)]")}>{selected && <Check size={13} />}</span>
                      <span className="flex-1">{option.name}</span>
                      <span className="font-mono text-[10px] uppercase text-[var(--faint)]">{option.code}</span>
                    </button>
                  );
                })}
                {filtered.length === 0 && <div className="px-3 py-10 text-center text-[12px] text-[var(--muted)]">No matching languages.</div>}
              </div>
              <div className="flex items-center justify-between border-t border-[var(--line)] px-5 py-3">
                <span className="text-[11px] text-[var(--muted)]">{draft.length}/8 selected</span>
                <button type="button" className="accent-button h-9 px-4 text-[11px] font-semibold" onClick={() => { onChange(draft); setOpen(false); setQuery(""); }}>Apply selection</button>
              </div>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
