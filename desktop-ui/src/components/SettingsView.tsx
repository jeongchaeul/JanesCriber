import { FolderOpen, Monitor, RotateCcw, Settings2, TerminalSquare } from "lucide-react";
import type { UpdateStatus } from "../types";

type InterfacePreference = "tauri" | "python";

interface SettingsViewProps {
  onSelectInterface: (preference: InterfacePreference, label: string) => void;
  onRelaunch: () => void;
  dataDirectory: string;
  onChooseDataDirectory: () => void;
  updateStatus: UpdateStatus;
  onCheckForUpdates: () => void;
  onOpenReleasePage: () => void;
}

export function SettingsView({ onSelectInterface, onRelaunch, dataDirectory, onChooseDataDirectory, updateStatus, onCheckForUpdates, onOpenReleasePage }: SettingsViewProps) {
  return (
    <section className="muted-scroll min-h-0 flex-1 overflow-y-auto p-7">
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Choose how JanesCriber opens and manage the application interface.</p>
        </div>

        <section className="panel p-5" aria-labelledby="interface-heading">
          <div className="flex items-start gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-cyan-300/25 bg-cyan-300/[.07] text-cyan-200">
              <Settings2 size={19} />
            </div>
            <div>
              <h2 id="interface-heading" className="text-[14px] font-semibold text-white">Interface</h2>
              <p className="mt-1 text-[11px] leading-5 text-[var(--muted)]">Select which launcher appears the next time JanesCriber starts. The change is saved beside the program.</p>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <button type="button" aria-label="Use Main UI next launch" onClick={() => onSelectInterface("tauri", "Main UI")} className="subtle-button flex min-h-16 items-center gap-3 px-4 py-3 text-left">
              <Monitor size={17} className="shrink-0 text-[var(--cyan)]" />
              <span>
                <span className="block text-[11px] font-semibold text-white">Use Main UI next launch</span>
                <span className="mt-1 block text-[10px] text-[var(--muted)]">Modern native Studio</span>
              </span>
            </button>
            <button type="button" aria-label="Use Legacy Python next launch" onClick={() => onSelectInterface("python", "Legacy Python UI")} className="subtle-button flex min-h-16 items-center gap-3 px-4 py-3 text-left">
              <TerminalSquare size={17} className="shrink-0 text-[var(--muted)]" />
              <span>
                <span className="block text-[11px] font-semibold text-white">Use Legacy Python next launch</span>
                <span className="mt-1 block text-[10px] text-[var(--muted)]">Original compatibility UI</span>
              </span>
            </button>
            <button type="button" aria-label="Relaunch JanesCriber" onClick={onRelaunch} className="subtle-button flex min-h-16 items-center gap-3 px-4 py-3 text-left">
              <RotateCcw size={17} className="shrink-0 text-[var(--muted)]" />
              <span>
                <span className="block text-[11px] font-semibold text-white">Relaunch JanesCriber</span>
                <span className="mt-1 block text-[10px] text-[var(--muted)]">Restart using the saved choice</span>
              </span>
            </button>
          </div>
        </section>

        <section className="panel p-5" aria-labelledby="local-data-heading">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 id="local-data-heading" className="text-[14px] font-semibold text-white">Local-first storage</h2>
              <p className="mt-2 max-w-2xl text-[11px] leading-5 text-[var(--muted)]">Models, caches, temporary files, and transcripts stay in this folder. Put it on another drive to keep large downloads away from C:.</p>
              <p className="mt-3 truncate rounded-md border border-[var(--line)] bg-black/[.15] px-3 py-2 font-mono text-[10px] text-[var(--cyan)]" title={dataDirectory}>{dataDirectory || "Loading data folder…"}</p>
            </div>
            <button type="button" aria-label="Choose data folder" onClick={onChooseDataDirectory} className="subtle-button flex h-9 shrink-0 items-center gap-2 px-3 text-[11px]"><FolderOpen size={14} /> Choose folder</button>
          </div>
          <p className="mt-3 text-[10px] text-[var(--faint)]">Changing this takes effect after relaunch. Existing files are not moved automatically.</p>
        </section>

        <section className="panel p-5" aria-labelledby="updates-heading">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 id="updates-heading" className="text-[14px] font-semibold text-white">Updates</h2>
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
              {(updateStatus.state === "available" || updateStatus.state === "not-ready") && <button type="button" aria-label="Open JanesCriber release page" onClick={onOpenReleasePage} className="accent-button flex h-9 items-center gap-2 px-3 text-[11px]">Open Releases</button>}
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}
