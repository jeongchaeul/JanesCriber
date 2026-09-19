import { AnimatePresence, motion } from "framer-motion";
import { AudioLines, ChevronLeft, ChevronRight, Cpu, FolderOpen, Radio, Settings2, TerminalSquare } from "lucide-react";
import type { ViewKey } from "../types";

const items: Array<{ key: ViewKey; label: string; icon: typeof AudioLines }> = [
  { key: "studio", label: "Transcription Studio", icon: AudioLines },
  { key: "library", label: "Transcript Library", icon: FolderOpen },
  { key: "live", label: "Live Transcription", icon: Radio },
  { key: "hardware", label: "Hardware & Pipeline", icon: Cpu },
  { key: "console", label: "Console Logs", icon: TerminalSquare },
  { key: "settings", label: "Settings", icon: Settings2 },
];

export function Sidebar({ activeView, collapsed, onChange, onToggle }: { activeView: ViewKey; collapsed: boolean; onChange: (view: ViewKey) => void; onToggle: () => void }) {
  return (
    <motion.aside
      animate={{ width: collapsed ? 76 : 258 }}
      transition={{ type: "spring", stiffness: 420, damping: 38 }}
      className="relative z-10 flex h-full shrink-0 flex-col border-r border-[var(--line)] bg-[rgba(8,8,16,.82)]"
    >
      <div className="flex h-16 items-center justify-between border-b border-[var(--line)] px-4">
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} className="text-[11px] font-semibold uppercase tracking-[.18em] text-[var(--faint)]">
              Workspace
            </motion.div>
          )}
        </AnimatePresence>
        <button type="button" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={onToggle} className="subtle-button ml-auto grid h-8 w-8 place-items-center">
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
      <div className="muted-scroll min-h-0 flex-1 overflow-y-auto">
      <div className="px-3 py-5">
        <div className={collapsed ? "flex justify-center" : "flex items-center gap-3 px-2"}>
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-cyan-300/35 bg-cyan-300/[.08] text-cyan-200">
            <AudioLines size={23} strokeWidth={1.7} />
          </div>
          <AnimatePresence initial={false}>
            {!collapsed && (
              <motion.div initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: "auto" }} exit={{ opacity: 0, width: 0 }} className="overflow-hidden whitespace-nowrap">
                <div className="text-[16px] font-semibold tracking-tight text-white">JanesCriber</div>
                <div className="mt-1 text-[9px] font-semibold uppercase tracking-[.16em] text-cyan-300/80">JANE MEDIA SUITE</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      <nav aria-label="Workspace navigation" className="flex flex-col gap-1 px-3">
        {items.map(({ key, label, icon: Icon }) => {
          const active = activeView === key;
          return (
            <button
              type="button"
              key={key}
              aria-current={active ? "page" : undefined}
              aria-label={collapsed ? label : undefined}
              title={collapsed ? label : undefined}
              onClick={() => onChange(key)}
              className={"group relative flex h-11 items-center gap-3 rounded-lg px-3 text-left text-[12px] transition-colors " + (active ? "bg-white/[.06] text-white" : "text-[var(--muted)] hover:bg-white/[.035] hover:text-white")}
            >
              <span className={"absolute left-0 h-5 w-[2px] rounded-full transition-opacity " + (active ? "bg-[var(--pink)] opacity-100" : "bg-transparent opacity-0")} />
              <Icon size={16} strokeWidth={active ? 2 : 1.7} className={active ? "text-[var(--pink)]" : "text-[var(--faint)] group-hover:text-[var(--muted)]"} />
              <AnimatePresence initial={false}>
                {!collapsed && <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="whitespace-nowrap">{label}</motion.span>}
              </AnimatePresence>
            </button>
          );
        })}
      </nav>
      </div>
      <div className="shrink-0 border-t border-[var(--line)] px-4 py-5">
        <div className={"flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.1em] text-[var(--green)] " + (collapsed ? "justify-center" : "")}>
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--green)]" />
          {!collapsed && <span>Local engine</span>}
        </div>
        {!collapsed && <div className="mt-2 text-[10px] leading-4 text-[var(--faint)]">Models, caches, and transcripts stay beside the program.</div>}
      </div>
    </motion.aside>
  );
}
