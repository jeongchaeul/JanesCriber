import { CircleHelp, FolderOpen, HardDrive, Paintbrush, Palette, Pipette, RefreshCw, RotateCcw } from "lucide-react";
import type { UpdateStatus } from "../types";

export const ACCENT_PRESETS = [
  { name: "Hot Pink (Default)", hex: "#c52b68" },
  { name: "Neon Rose", hex: "#f43f5e" },
  { name: "Electric Purple", hex: "#8b5cf6" },
  { name: "Cyber Cyan", hex: "#06b6d4" },
  { name: "Sky Blue", hex: "#3b82f6" },
  { name: "Emerald Green", hex: "#10b981" },
  { name: "Amber Gold", hex: "#f59e0b" },
  { name: "Sunset Coral", hex: "#f97316" },
];

export const BG_PRESETS = [
  { name: "Void Black (Default)", hex: "#02000a" },
  { name: "Deep Obsidian", hex: "#09090b" },
  { name: "Midnight Navy", hex: "#0b0f17" },
  { name: "Abyssal Plum", hex: "#12071a" },
  { name: "Rosy Pearl (Light)", hex: "#fdf7fa" },
  { name: "Pure White", hex: "#ffffff" },
  { name: "Soft Zinc", hex: "#f4f4f5" },
  { name: "Warm Cream", hex: "#faf8f5" },
];

export interface SettingsViewProps {
  onRelaunch: () => void;
  dataDirectory: string;
  onChooseDataDirectory: () => void;
  updateStatus: UpdateStatus;
  onCheckForUpdates: () => void;
  onOpenReleasePage: () => void;
  accentColor?: string;
  bgColor?: string;
  onAccentColorChange?: (color: string) => void;
  onBgColorChange?: (color: string) => void;
  onResetColors?: () => void;
  onOpenHelp?: () => void;
  onSelectInterface?: (preference: string, label: string) => void;
}

export function SettingsView({
  onRelaunch,
  dataDirectory,
  onChooseDataDirectory,
  updateStatus,
  onCheckForUpdates,
  onOpenReleasePage,
  accentColor = "#c52b68",
  bgColor = "#02000a",
  onAccentColorChange,
  onBgColorChange,
  onResetColors,
  onOpenHelp,
}: SettingsViewProps) {
  return (
    <section className="muted-scroll min-h-0 flex-1 overflow-y-auto p-7">
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Customize application appearance, local storage, interface selection, and updates.</p>
        </div>

        {/* Interface Theme & Color Palette (JaneConverter Parity) */}
        <section className="panel p-5 space-y-4" aria-labelledby="theme-heading">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Palette size={17} style={{ color: "var(--accent-color, #c52b68)" }} />
                <h2 id="theme-heading" className="inline text-[14px] font-semibold text-white">Interface Theme & Color Palette</h2>
              </div>
              <p className="mt-1 text-xs text-[var(--muted)]">
                Personalize JanesCriber in real-time. Pick custom accent & background colors or choose preset styles.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {onOpenHelp && (
                <button
                  type="button"
                  onClick={onOpenHelp}
                  className="subtle-button flex items-center gap-1.5 px-3 py-1.5 text-xs hover:text-white"
                  title="Open quick guide"
                >
                  <CircleHelp className="size-3" /> Quick guide
                </button>
              )}
              <button
                type="button"
                onClick={() => onResetColors?.()}
                className="subtle-button flex items-center gap-1.5 px-3 py-1.5 text-xs hover:text-white"
                title="Reset accent and background to default"
              >
                <RotateCcw className="size-3" /> Reset colors
              </button>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 pt-2 border-t border-white/[0.06]">
            {/* Accent Color Customizer */}
            <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3.5">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-medium text-zinc-200 flex items-center gap-1.5">
                  <Pipette className="size-3.5" style={{ color: "var(--accent-color, #c52b68)" }} />
                  Accent Color
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    aria-label="Accent color picker"
                    value={accentColor}
                    onChange={(event) => onAccentColorChange?.(event.target.value)}
                    className="size-7 cursor-pointer rounded-lg border border-white/20 bg-transparent p-0.5"
                  />
                  <span className="font-mono text-xs uppercase text-zinc-400">{accentColor}</span>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                {ACCENT_PRESETS.map((swatch) => (
                  <button
                    key={swatch.hex}
                    type="button"
                    onClick={() => onAccentColorChange?.(swatch.hex)}
                    title={swatch.name}
                    className={`size-6 rounded-lg transition-transform hover:scale-110 relative ${
                      accentColor.toLowerCase() === swatch.hex.toLowerCase()
                        ? "ring-2 ring-white ring-offset-2 ring-offset-black scale-105"
                        : "border border-white/10"
                    }`}
                    style={{ backgroundColor: swatch.hex }}
                  />
                ))}
              </div>
            </div>

            {/* Main Theme Color (Background) Customizer */}
            <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3.5">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-medium text-zinc-200 flex items-center gap-1.5">
                  <Paintbrush className="size-3.5 text-zinc-400" />
                  Main Theme Color (Background)
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    aria-label="Theme background color picker"
                    value={bgColor}
                    onChange={(event) => onBgColorChange?.(event.target.value)}
                    className="size-7 cursor-pointer rounded-lg border border-white/20 bg-transparent p-0.5"
                  />
                  <span className="font-mono text-xs uppercase text-zinc-400">{bgColor}</span>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                {BG_PRESETS.map((swatch) => (
                  <button
                    key={swatch.hex}
                    type="button"
                    onClick={() => onBgColorChange?.(swatch.hex)}
                    title={swatch.name}
                    className={`size-6 rounded-lg transition-transform hover:scale-110 relative ${
                      bgColor.toLowerCase() === swatch.hex.toLowerCase()
                        ? "ring-2 ring-white ring-offset-2 ring-offset-black scale-105"
                        : "border border-white/10"
                    }`}
                    style={{ backgroundColor: swatch.hex }}
                  />
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Local-First Storage Section */}
        <section className="panel p-5" aria-labelledby="local-data-heading">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <HardDrive size={16} className="text-[var(--muted)]" />
                <h2 id="local-data-heading" className="text-[14px] font-semibold text-white">Local-first storage</h2>
              </div>
              <p className="mt-2 max-w-2xl text-[11px] leading-5 text-[var(--muted)]">Models, caches, temporary files, and transcripts stay in this folder. Put it on another drive to keep large downloads away from C:.</p>
              <p className="mt-3 truncate rounded-md border border-[var(--line)] bg-black/[.25] px-3 py-2 font-mono text-[10px] text-[var(--cyan)]" title={dataDirectory}>{dataDirectory || "Loading data folder…"}</p>
            </div>
            <div className="flex shrink-0 flex-wrap justify-end gap-2">
              <button type="button" aria-label="Choose data folder" onClick={onChooseDataDirectory} className="subtle-button flex h-9 shrink-0 items-center gap-2 px-3 text-[11px]"><FolderOpen size={14} /> Choose folder</button>
              <button type="button" aria-label="Relaunch JanesCriber" onClick={onRelaunch} className="subtle-button flex h-9 shrink-0 items-center gap-2 px-3 text-[11px]"><RotateCcw size={14} /> Relaunch Studio</button>
            </div>
          </div>
          <p className="mt-3 text-[10px] text-[var(--faint)]">Changing data folder takes effect after relaunch. Existing files are not moved automatically.</p>
        </section>

        {/* Updates Section */}
        <section className="panel p-5" aria-labelledby="updates-heading">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <RefreshCw size={16} className="text-[var(--muted)]" />
                <h2 id="updates-heading" className="text-[14px] font-semibold text-white">Updates</h2>
              </div>
              <p className="mt-2 max-w-2xl text-[11px] leading-5 text-[var(--muted)]">Studio checks the official JanesCriber GitHub Releases page. Your transcripts, models, and selected data folder are not replaced by an update.</p>
              <p className="mt-3 text-[10px] text-[var(--faint)]" role="status" aria-live="polite">
                {updateStatus.state === "checking" && "Checking for the latest release…"}
                {updateStatus.state === "current" && `JanesCriber ${updateStatus.currentVersion} is up to date. Checked ${updateStatus.checkedAt}.`}
                {updateStatus.state === "available" && `JanesCriber ${updateStatus.latestVersion} is available. Download it from the official release page.`}
                {updateStatus.state === "not-ready" && `JanesCriber ${updateStatus.latestVersion} exists, but its installer is not published yet.`}
                {updateStatus.state === "offline" && updateStatus.message}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap justify-end gap-2">
              <button type="button" aria-label="Check for updates" onClick={onCheckForUpdates} className="subtle-button flex h-9 items-center gap-2 px-3 text-[11px]" disabled={updateStatus.state === "checking"}>
                <RotateCcw size={14} /> Check for updates
              </button>
              {(updateStatus.state === "available" || updateStatus.state === "not-ready") && (
                <button type="button" aria-label="Open JanesCriber release page" onClick={onOpenReleasePage} className="accent-button flex h-9 items-center gap-2 px-3 text-[11px]">
                  Open Releases
                </button>
              )}
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}
