import { motion } from "framer-motion";
import { LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { chooseDataDirectory, getAppVersion, getDataDirectory, openReleasePage, relaunchLauncher, request, setDataDirectory, setFrontendPreference, stopBackend, subscribe } from "./bridge";
import { ConsoleView } from "./components/ConsoleView";
import { HardwareView } from "./components/HardwareView";
import { LibraryView } from "./components/LibraryView";
import { LiveView } from "./components/LiveView";
import { Sidebar } from "./components/Sidebar";
import { SettingsView } from "./components/SettingsView";
import { StudioView } from "./components/StudioView";
import { checkForUpdates } from "./updates";
import type { BackendMessage, Bootstrap, LogLine, UpdateStatus, ViewKey } from "./types";

const titles: Record<ViewKey, string> = {
  studio: "Transcription Studio",
  library: "Transcript Library",
  live: "Live Transcription",
  hardware: "Hardware & Pipeline",
  console: "Console Logs",
  settings: "Settings",
};

export default function App() {
  const [activeView, setActiveView] = useState<ViewKey>("studio");
  const [collapsed, setCollapsed] = useState(false);
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [latestMessage, setLatestMessage] = useState<BackendMessage | null>(null);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [liveActive, setLiveActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState("Waiting for a transcription request.");
  const [dataDirectory, setDataDirectoryState] = useState("");
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>({ state: "checking", currentVersion: "" });

  const addLog = useCallback((message: string, tone: LogLine["tone"] = "normal") => {
    setLogs((current) => [...current.slice(-399), { id: Date.now() + current.length, message, tone, at: new Date().toLocaleTimeString() }]);
  }, []);

  useEffect(() => {
    let mounted = true;
    let unsubscribe: (() => void) | undefined;
    void subscribe((message) => {
      if (!mounted) return;
      setLatestMessage(message);
      if (message.type === "event") {
        const event = String(message.event || "");
        if (event === "log") addLog(String(message.message || ""));
        if (event === "progress") { const value = Number(message.progress || 0); setProgress(value); setProgressMessage(String(message.message || "")); addLog(String(message.message || "")); }
        if (event === "completed") addLog("Completed successfully: " + String(message.output || ""), "success");
        if (event === "cancelled") addLog(String(message.message || "Transcription cancelled."), "warning");
        if (event === "error" || event === "live-error") addLog(String(message.message || "The local engine reported an error."), "error");
        if (event === "live-status") addLog(String(message.message || ""));
        if (event === "live-finished") addLog("Live transcript saved: " + String(message.output || ""), "success");
      }
    }).then((unlisten) => { unsubscribe = unlisten; }).catch((error) => addLog("Could not subscribe to the local engine: " + String(error), "error"));
    void getDataDirectory().then((value) => { if (mounted) setDataDirectoryState(value); }).catch((error) => addLog("Could not read the data folder: " + String(error), "error"));
    void request<Bootstrap>("bootstrap").then((value) => { if (mounted) { setBootstrap(value); addLog("JanesCriber Studio ready. Project folder: " + value.projectRoot, "success"); } }).catch((error) => addLog("Local engine is unavailable: " + String(error), "error"));
    return () => { mounted = false; unsubscribe?.(); void stopBackend().catch(() => undefined); };
  }, [addLog]);

  const onCheckForUpdates = useCallback(async () => {
    setUpdateStatus((current) => ({ state: "checking", currentVersion: current.currentVersion }));
    try {
      const version = await getAppVersion();
      const result = await checkForUpdates(version);
      setUpdateStatus(result);
      if (result.state === "available") addLog(`Update available: JanesCriber ${result.latestVersion}.`, "warning");
    } catch (error) {
      setUpdateStatus({ state: "offline", currentVersion: "", message: String(error) });
    }
  }, [addLog]);

  useEffect(() => { void onCheckForUpdates(); }, [onCheckForUpdates]);

  const onOpenReleasePage = useCallback(async () => {
    try {
      await openReleasePage();
    } catch (error) {
      addLog(`Could not open the JanesCriber Releases page: ${String(error)}`, "error");
    }
  }, [addLog]);

  const onBusy = useCallback((value: boolean) => setBusy(value), []);
  const onLiveState = useCallback((value: boolean) => setLiveActive(value), []);
  const onProgress = useCallback((value: number, message: string) => { setProgress(value); setProgressMessage(message); }, []);
  const onLibraryRefresh = useCallback(() => setRefreshKey((value) => value + 1), []);
  const onSelectInterface = useCallback(async (preference: "tauri" | "python", label: string) => {
    try {
      await setFrontendPreference(preference);
      addLog(`${label} selected for the next launch.`, "success");
    } catch (error) {
      addLog(`Could not save the interface preference: ${String(error)}`, "error");
    }
  }, [addLog]);
  const onRelaunch = useCallback(async () => {
    try {
      addLog("Relaunching JanesCriber…");
      await relaunchLauncher();
    } catch (error) {
      addLog(`Could not relaunch JanesCriber: ${String(error)}`, "error");
    }
  }, [addLog]);
  const onChooseDataDirectory = useCallback(async () => {
    try {
      const selected = await chooseDataDirectory();
      if (!selected) return;
      const saved = await setDataDirectory(selected);
      setDataDirectoryState(saved);
      addLog(`Data folder saved for the next launch: ${saved}`, "success");
    } catch (error) {
      addLog(`Could not save the data folder: ${String(error)}`, "error");
    }
  }, [addLog]);

  return (
    <div className="shell-bg flex h-screen overflow-hidden">
      <Sidebar activeView={activeView} collapsed={collapsed} onChange={setActiveView} onToggle={() => setCollapsed((value) => !value)} />
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-[var(--line)] px-7">
          <div className="flex items-center gap-3"><span className="text-[11px] font-semibold uppercase tracking-[.16em] text-[var(--faint)]">{titles[activeView]}</span>{busy && <span className="flex items-center gap-2 text-[10px] text-[var(--yellow)]"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--yellow)]" /> processing</span>}{liveActive && <span className="flex items-center gap-2 text-[10px] text-[var(--green)]"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--green)]" /> live</span>}</div>
          <div className="flex items-center gap-3 text-[10px] text-[var(--muted)]"><span className="hidden sm:inline">Local-first · project-local data</span><span className="h-1.5 w-1.5 rounded-full bg-[var(--cyan)]" />{String(bootstrap?.hardware?.accelerator || "connecting")}</div>
        </div>
        <div className="relative min-h-0 flex-1">
          <motion.div animate={{ opacity: activeView === "studio" ? 1 : 0, y: activeView === "studio" ? 0 : 4 }} transition={{ duration: .18 }} className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "studio" ? "visible" : "invisible pointer-events-none")}><StudioView bootstrap={bootstrap} logs={logs} message={latestMessage} onBusy={onBusy} onProgress={onProgress} onLibraryRefresh={onLibraryRefresh} onOpenConsole={() => setActiveView("console")} /></motion.div>
          <motion.div animate={{ opacity: activeView === "library" ? 1 : 0, y: activeView === "library" ? 0 : 4 }} transition={{ duration: .18 }} className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "library" ? "visible" : "invisible pointer-events-none")}><LibraryView bootstrap={bootstrap} refreshKey={refreshKey} /></motion.div>
          <motion.div animate={{ opacity: activeView === "live" ? 1 : 0, y: activeView === "live" ? 0 : 4 }} transition={{ duration: .18 }} className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "live" ? "visible" : "invisible pointer-events-none")}><LiveView bootstrap={bootstrap} message={latestMessage} visible={activeView === "live"} onLibraryRefresh={onLibraryRefresh} onLiveState={onLiveState} /></motion.div>
          <motion.div animate={{ opacity: activeView === "hardware" ? 1 : 0, y: activeView === "hardware" ? 0 : 4 }} transition={{ duration: .18 }} className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "hardware" ? "visible" : "invisible pointer-events-none")}><HardwareView bootstrap={bootstrap} active={busy || liveActive} visible={activeView === "hardware"} progress={progress} progressMessage={progressMessage} /></motion.div>
          <motion.div animate={{ opacity: activeView === "console" ? 1 : 0, y: activeView === "console" ? 0 : 4 }} transition={{ duration: .18 }} className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "console" ? "visible" : "invisible pointer-events-none")}><ConsoleView logs={logs} onClear={() => setLogs([])} /></motion.div>
          <motion.div animate={{ opacity: activeView === "settings" ? 1 : 0, y: activeView === "settings" ? 0 : 4 }} transition={{ duration: .18 }} className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "settings" ? "visible" : "invisible pointer-events-none")}><SettingsView onSelectInterface={onSelectInterface} onRelaunch={onRelaunch} dataDirectory={dataDirectory} onChooseDataDirectory={onChooseDataDirectory} updateStatus={updateStatus} onCheckForUpdates={onCheckForUpdates} onOpenReleasePage={onOpenReleasePage} /></motion.div>
        </div>
      </main>
      {!bootstrap && <div className="pointer-events-none fixed bottom-5 right-5 flex items-center gap-2 rounded-lg border border-[var(--line)] bg-[var(--surface-raised)] px-3 py-2 text-[10px] text-[var(--muted)] shadow-xl"><LoaderCircle size={13} className="animate-spin text-[var(--cyan)]" /> Connecting to local engine…</div>}
    </div>
  );
}
