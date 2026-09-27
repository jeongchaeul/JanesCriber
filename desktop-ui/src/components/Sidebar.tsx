import { Activity, AudioLines, Cpu, FolderOpen, PanelLeftClose, PanelLeftOpen, Radio, Settings2, TerminalSquare } from "lucide-react";
import { motion } from "framer-motion";
import type { ViewKey } from "../types";

const items: Array<{ key: ViewKey; label: string; icon: typeof AudioLines }> = [
  { key: "studio", label: "Transcription Studio", icon: AudioLines },
  { key: "library", label: "Transcript Library", icon: FolderOpen },
  { key: "live", label: "Live Transcription", icon: Radio },
  { key: "hardware", label: "Hardware & Pipeline", icon: Cpu },
  { key: "console", label: "Console Logs", icon: TerminalSquare },
  { key: "settings", label: "Settings", icon: Settings2 },
];

export function Sidebar({
  activeView,
  collapsed,
  onChange,
  onToggle,
  busy = false,
  liveActive = false,
}: {
  activeView: ViewKey;
  collapsed: boolean;
  onChange: (view: ViewKey) => void;
  onToggle: () => void;
  busy?: boolean;
  liveActive?: boolean;
}) {
  return (
    <motion.aside
      data-collapsed={collapsed}
      animate={{ width: collapsed ? 76 : 232 }}
      transition={{ type: "spring", stiffness: 420, damping: 38 }}
      className="relative z-10 flex shrink-0 flex-col overflow-hidden border-r border-white/[0.06] bg-[#05040d]/85 px-4 py-5 backdrop-blur-xl"
    >
      {/* Brand Header with Glowing Accent Orb (JaneConverter Parity) */}
      <div className={["flex min-h-9 items-center gap-3", collapsed ? "justify-center" : "justify-start"].join(" ")}>
        <div className="grid size-9 shrink-0 place-items-center rounded-xl border border-white/10 bg-[#11101b] shadow-[0_8px_24px_rgba(0,0,0,.28)]">
          <span
            className="size-2 rounded-full"
            style={{
              backgroundColor: "var(--accent-color, #c52b68)",
              boxShadow: "0 0 14px var(--accent-glow, rgba(197,43,104,.55))",
            }}
          />
        </div>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold tracking-tight text-white">JanesCriber</div>
            <div className="mono-label mt-0.5">LOCAL / STUDIO</div>
          </div>
        )}
      </div>

      {!collapsed && <div className="mono-label mt-8 px-3">Workspace</div>}

      {/* Navigation list with smooth layoutId animation */}
      <nav className="mt-3 flex-1 space-y-1" aria-label="Primary">
        {items.map(({ key, label, icon: Icon }) => {
          const active = activeView === key;
          return (
            <button
              key={key}
              type="button"
              aria-current={active ? "page" : undefined}
              aria-label={label}
              title={collapsed ? label : undefined}
              onClick={() => onChange(key)}
              className={[
                "group relative flex w-full items-center rounded-xl py-2.5 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#3b82f6]",
                collapsed ? "justify-center px-2" : "gap-3 px-3",
                active ? "text-white" : "text-zinc-500 hover:bg-white/[0.035] hover:text-zinc-200",
              ].join(" ")}
            >
              {active && (
                <motion.span
                  layoutId="active-nav"
                  className="absolute inset-0 rounded-xl border bg-white/[0.045]"
                  style={{ borderColor: "var(--accent-glow, rgba(197,43,104,0.35))" }}
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                />
              )}
              <Icon
                className={["relative z-10 size-4", active ? "" : "text-zinc-600 group-hover:text-zinc-300"].join(" ")}
                style={active ? { color: "var(--accent-color, #d75b88)" } : undefined}
                strokeWidth={1.8}
              />
              {!collapsed && <span className="relative z-10 truncate text-[13px]">{label}</span>}
              {key === "studio" && busy && (
                <span
                  className={collapsed ? "absolute top-1.5 right-1.5 size-1.5 rounded-full bg-amber-400 animate-pulse" : "relative z-10 ml-auto size-1.5 rounded-full bg-amber-400 animate-pulse"}
                  title="Transcription processing"
                />
              )}
              {key === "live" && liveActive && (
                <span
                  className={collapsed ? "absolute top-1.5 right-1.5 size-1.5 rounded-full bg-emerald-400 animate-pulse" : "relative z-10 ml-auto size-1.5 rounded-full bg-emerald-400 animate-pulse"}
                  title="Live capture active"
                />
              )}
            </button>
          );
        })}

        {/* Collapse / Expand Toggle Button */}
        <div className="mt-2 border-t border-white/[0.06] pt-2">
          <button
            type="button"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={onToggle}
            className={[
              "group flex w-full items-center rounded-xl py-2.5 text-left text-xs text-zinc-500 transition-colors hover:bg-white/[0.035] hover:text-zinc-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#3b82f6]",
              collapsed ? "justify-center px-2" : "gap-3 px-3",
            ].join(" ")}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-4 text-zinc-600 group-hover:text-zinc-300" />
            ) : (
              <PanelLeftClose className="size-4 text-zinc-600 group-hover:text-zinc-300" />
            )}
            {!collapsed && <span className="truncate">Collapse sidebar</span>}
          </button>
        </div>

        {/* Local-first status indicator placed directly below collapse button (JaneConverter Parity) */}
        {!collapsed && (
          <div className="mt-3 shrink-0 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-3">
            <div className="flex items-center gap-2 text-xs text-zinc-300">
              <Activity className="size-3.5 text-zinc-500" />
              <span>Project-local workspace</span>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-500">
              Media, temporary files, settings, and logs stay beside JanesCriber.
            </p>
          </div>
        )}
      </nav>
    </motion.aside>
  );
}
