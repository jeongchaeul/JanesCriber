import { Monitor, RotateCcw, Settings2, TerminalSquare } from "lucide-react";

type InterfacePreference = "tauri" | "python";

interface SettingsViewProps {
  onSelectInterface: (preference: InterfacePreference, label: string) => void;
  onRelaunch: () => void;
}

export function SettingsView({ onSelectInterface, onRelaunch }: SettingsViewProps) {
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
          <h2 id="local-data-heading" className="text-[14px] font-semibold text-white">Local-first storage</h2>
          <p className="mt-2 max-w-2xl text-[11px] leading-5 text-[var(--muted)]">Models, caches, temporary files, and transcripts stay beside JanesCriber whenever the selected engine supports local storage.</p>
        </section>
      </div>
    </section>
  );
}
