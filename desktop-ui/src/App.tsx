import { AnimatePresence, motion } from "framer-motion";
import { LoaderCircle, UploadCloud, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  chooseDataDirectory,
  getAppVersion,
  getDataDirectory,
  onFileDragDrop,
  openReleasePage,
  relaunchLauncher,
  request,
  setDataDirectory,
  setFrontendPreference,
  stopBackend,
  subscribe,
} from "./bridge";
import { ConsoleView } from "./components/ConsoleView";
import { HardwareView } from "./components/HardwareView";
import { LibraryView } from "./components/LibraryView";
import { LiveView } from "./components/LiveView";
import { Sidebar } from "./components/Sidebar";
import { SettingsView } from "./components/SettingsView";
import { StudioView } from "./components/StudioView";
import { checkForUpdates } from "./updates";
import type { BackendMessage, Bootstrap, LogLine, UpdateStatus, ViewKey } from "./types";

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
  const [helpOpen, setHelpOpen] = useState(false);
  const [windowDragging, setWindowDragging] = useState(false);
  const [droppedSource, setDroppedSource] = useState<string | null>(null);

  // Native & Window-wide Drag and Drop Support (JaneConverter Parity)
  useEffect(() => {
    const preventDrag = (e: DragEvent) => e.preventDefault();
    window.addEventListener("dragover", preventDrag);
    window.addEventListener("drop", preventDrag);

    let unlisten: (() => void) | undefined;
    onFileDragDrop((event) => {
      if (event.type === "enter" || event.type === "over") {
        setWindowDragging(true);
      } else if (event.type === "leave") {
        setWindowDragging(false);
      } else if (event.type === "drop") {
        setWindowDragging(false);
        if (event.paths && event.paths.length > 0) {
          setDroppedSource(event.paths[0]);
          setActiveView("studio");
        }
      }
    }).then((fn) => {
      unlisten = fn;
    });

    return () => {
      window.removeEventListener("dragover", preventDrag);
      window.removeEventListener("drop", preventDrag);
      unlisten?.();
    };
  }, []);

  // Dynamic Theme & Color Customization (JaneConverter Parity)
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof window === "undefined") return "dark";
    try {
      return (window.localStorage.getItem("janescriber.theme") as "light" | null) ?? "dark";
    } catch {
      return "dark";
    }
  });

  const [accentColor, setAccentColor] = useState<string>(() => {
    if (typeof window === "undefined") return "#c52b68";
    try {
      return window.localStorage.getItem("janescriber.accentColor") ?? "#c52b68";
    } catch {
      return "#c52b68";
    }
  });

  const [bgColor, setBgColor] = useState<string>(() => {
    if (typeof window === "undefined") return "#02000a";
    try {
      return window.localStorage.getItem("janescriber.bgColor") ?? "#02000a";
    } catch {
      return "#02000a";
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    const clean = accentColor.replace("#", "");
    const full = clean.length === 3 ? clean.split("").map((c) => c + c).join("") : clean;
    const num = parseInt(full, 16);
    const r = isNaN(num) ? 197 : (num >> 16) & 255;
    const g = isNaN(num) ? 43 : (num >> 8) & 255;
    const b = isNaN(num) ? 104 : num & 255;

    const clamp = (v: number) => Math.min(255, Math.max(0, Math.round(v * 1.15)));
    const hoverHex = `#${clamp(r).toString(16).padStart(2, "0")}${clamp(g).toString(16).padStart(2, "0")}${clamp(b).toString(16).padStart(2, "0")}`;

    root.style.setProperty("--accent-color", accentColor);
    root.style.setProperty("--accent-hover", hoverHex);
    root.style.setProperty("--accent-glow", `rgba(${r}, ${g}, ${b}, 0.35)`);
    root.style.setProperty("--accent-subtle", `rgba(${r}, ${g}, ${b}, 0.12)`);
    root.style.setProperty("--bg-color", bgColor);

    try {
      window.localStorage.setItem("janescriber.theme", theme);
      window.localStorage.setItem("janescriber.accentColor", accentColor);
      window.localStorage.setItem("janescriber.bgColor", bgColor);
    } catch {}
  }, [theme, accentColor, bgColor]);

  function handleAccentChange(color: string) {
    setAccentColor(color);
  }

  function handleBgChange(color: string) {
    setBgColor(color);
    const clean = color.replace("#", "");
    const full = clean.length === 3 ? clean.split("").map((c) => c + c).join("") : clean;
    const num = parseInt(full, 16);
    if (!isNaN(num)) {
      const r = (num >> 16) & 255;
      const g = (num >> 8) & 255;
      const b = num & 255;
      const isLight = (r * 299 + g * 587 + b * 114) / 1000 > 135;
      if (isLight && theme !== "light") {
        setTheme("light");
      } else if (!isLight && theme !== "dark") {
        setTheme("dark");
      }
    }
  }

  function handleResetColors() {
    setTheme("dark");
    setAccentColor("#c52b68");
    setBgColor("#02000a");
  }

  const addLog = useCallback((message: string, tone: LogLine["tone"] = "normal") => {
    setLogs((current) => [
      ...current.slice(-399),
      { id: Date.now() + current.length, message, tone, at: new Date().toLocaleTimeString() },
    ]);
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
        if (event === "progress") {
          const value = Number(message.progress || 0);
          setProgress(value);
          setProgressMessage(String(message.message || ""));
          addLog(String(message.message || ""));
        }
        if (event === "completed") addLog("Completed successfully: " + String(message.output || ""), "success");
        if (event === "cancelled") addLog(String(message.message || "Transcription cancelled."), "warning");
        if (event === "error" || event === "live-error") addLog(String(message.message || "The local engine reported an error."), "error");
        if (event === "live-status") addLog(String(message.message || ""));
        if (event === "live-finished") addLog("Live transcript saved: " + String(message.output || ""), "success");
      }
    })
      .then((unlisten) => {
        unsubscribe = unlisten;
      })
      .catch((error) => addLog("Could not subscribe to the local engine: " + String(error), "error"));

    void getDataDirectory()
      .then((value) => {
        if (mounted) setDataDirectoryState(value);
      })
      .catch((error) => addLog("Could not read the data folder: " + String(error), "error"));

    void request<Bootstrap>("bootstrap")
      .then((value) => {
        if (mounted) {
          setBootstrap(value);
          addLog("JanesCriber Studio ready. Project folder: " + value.projectRoot, "success");
        }
      })
      .catch((error) => addLog("Local engine is unavailable: " + String(error), "error"));

    return () => {
      mounted = false;
      unsubscribe?.();
      void stopBackend().catch(() => undefined);
    };
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

  useEffect(() => {
    void onCheckForUpdates();
  }, [onCheckForUpdates]);

  const onOpenReleasePage = useCallback(async () => {
    try {
      await openReleasePage();
    } catch (error) {
      addLog(`Could not open the JanesCriber Releases page: ${String(error)}`, "error");
    }
  }, [addLog]);

  const onBusy = useCallback((value: boolean) => setBusy(value), []);
  const onLiveState = useCallback((value: boolean) => setLiveActive(value), []);
  const onProgress = useCallback((value: number, message: string) => {
    setProgress(value);
    setProgressMessage(message);
  }, []);
  const onLibraryRefresh = useCallback(() => setRefreshKey((value) => value + 1), []);
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

  useEffect(() => {
    if (!helpOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setHelpOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [helpOpen]);

  return (
    <div className="shell-bg relative flex h-screen overflow-hidden">
      {/* Ambient background glow orb (JaneConverter Parity) */}
      <div className="ambient-orb top-right-glow pointer-events-none absolute -right-36 -top-36 h-96 w-96 rounded-full opacity-35" />

      <Sidebar
        activeView={activeView}
        collapsed={collapsed}
        onChange={setActiveView}
        onToggle={() => setCollapsed((value) => !value)}
        busy={busy}
        liveActive={liveActive}
      />

      <main className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {/* View Switcher Container */}
        <div className="relative min-h-0 flex-1">
          <motion.div
            animate={{ opacity: activeView === "studio" ? 1 : 0, y: activeView === "studio" ? 0 : 4 }}
            transition={{ duration: 0.18 }}
            className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "studio" ? "visible" : "invisible pointer-events-none")}
          >
            <StudioView
              bootstrap={bootstrap}
              logs={logs}
              message={latestMessage}
              onBusy={onBusy}
              onProgress={onProgress}
              onLibraryRefresh={onLibraryRefresh}
              onOpenConsole={() => setActiveView("console")}
              droppedFile={droppedSource}
              onClearDroppedFile={() => setDroppedSource(null)}
            />
          </motion.div>
          <motion.div
            animate={{ opacity: activeView === "library" ? 1 : 0, y: activeView === "library" ? 0 : 4 }}
            transition={{ duration: 0.18 }}
            className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "library" ? "visible" : "invisible pointer-events-none")}
          >
            <LibraryView bootstrap={bootstrap} refreshKey={refreshKey} />
          </motion.div>
          <motion.div
            animate={{ opacity: activeView === "live" ? 1 : 0, y: activeView === "live" ? 0 : 4 }}
            transition={{ duration: 0.18 }}
            className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "live" ? "visible" : "invisible pointer-events-none")}
          >
            <LiveView
              bootstrap={bootstrap}
              message={latestMessage}
              visible={activeView === "live"}
              onLibraryRefresh={onLibraryRefresh}
              onLiveState={onLiveState}
            />
          </motion.div>
          <motion.div
            animate={{ opacity: activeView === "hardware" ? 1 : 0, y: activeView === "hardware" ? 0 : 4 }}
            transition={{ duration: 0.18 }}
            className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "hardware" ? "visible" : "invisible pointer-events-none")}
          >
            <HardwareView
              bootstrap={bootstrap}
              active={busy || liveActive}
              visible={activeView === "hardware"}
              progress={progress}
              progressMessage={progressMessage}
            />
          </motion.div>
          <motion.div
            animate={{ opacity: activeView === "console" ? 1 : 0, y: activeView === "console" ? 0 : 4 }}
            transition={{ duration: 0.18 }}
            className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "console" ? "visible" : "invisible pointer-events-none")}
          >
            <ConsoleView logs={logs} onClear={() => setLogs([])} />
          </motion.div>
          <motion.div
            animate={{ opacity: activeView === "settings" ? 1 : 0, y: activeView === "settings" ? 0 : 4 }}
            transition={{ duration: 0.18 }}
            className={"absolute inset-0 flex h-full min-h-0 " + (activeView === "settings" ? "visible" : "invisible pointer-events-none")}
          >
            <SettingsView
              onRelaunch={onRelaunch}
              dataDirectory={dataDirectory}
              onChooseDataDirectory={onChooseDataDirectory}
              updateStatus={updateStatus}
              onCheckForUpdates={onCheckForUpdates}
              onOpenReleasePage={onOpenReleasePage}
              accentColor={accentColor}
              bgColor={bgColor}
              onAccentColorChange={handleAccentChange}
              onBgColorChange={handleBgChange}
              onResetColors={handleResetColors}
              onOpenHelp={() => setHelpOpen(true)}
            />
          </motion.div>
        </div>
      </main>

      {/* Full-Window Drag & Drop Overlay (JaneConverter Parity) */}
      <AnimatePresence>
        {windowDragging && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none fixed inset-0 z-[9998] flex flex-col items-center justify-center bg-[#02000a]/85 backdrop-blur-md"
          >
            <div className="flex flex-col items-center gap-4 rounded-3xl border-2 border-dashed border-[var(--accent-color,#c52b68)] bg-[var(--accent-subtle,rgba(197,43,104,0.12))] p-12 text-center shadow-2xl">
              <div className="grid size-16 place-items-center rounded-2xl bg-[var(--accent-color,#c52b68)]/20 text-[var(--accent-color,#c52b68)] shadow-[0_0_30px_var(--accent-glow,rgba(197,43,104,0.4))]">
                <UploadCloud className="size-8 animate-bounce" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">Drop to Transcribe</h3>
                <p className="mt-1 text-sm text-zinc-400">
                  Audio and video files will be immediately loaded into Transcription Studio
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Quick Guide Help Modal (JaneConverter Parity with solid background and portal) */}
      {helpOpen &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="fixed inset-0 z-[9999] grid place-items-center bg-black/75 p-6 backdrop-blur-md"
            role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setHelpOpen(false);
            }}
          >
            <section
              className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-white/15 bg-[#0d0c18] p-6 shadow-2xl shadow-black/90"
              role="dialog"
              aria-modal="true"
              aria-labelledby="janescriber-help-title"
            >
              <button
                type="button"
                onClick={() => setHelpOpen(false)}
                className="absolute right-4 top-4 grid size-8 place-items-center rounded-lg text-zinc-400 hover:bg-white/[0.06] hover:text-white"
                aria-label="Close help"
              >
                <X className="size-4" />
              </button>
              <div className="mono-label">Quick guide</div>
              <h2 id="janescriber-help-title" className="mt-2 text-xl font-semibold text-white">
                Using JanesCriber
              </h2>
              <div className="mt-4 space-y-3 text-xs leading-relaxed text-zinc-400">
                <p>
                  <span className="font-medium text-white">Transcribe Media:</span> Drag and drop an audio or video file anywhere into JanesCriber, pick an ASR engine and model, and click Transcribe (or press Ctrl+Enter).
                </p>
                <p>
                  <span className="font-medium text-white">Live Capture:</span> Open Live Transcription to capture from your microphone, speaker output loopback, or a specific application.
                </p>
                <p>
                  <span className="font-medium text-white">Hardware Telemetry:</span> Hardware & Pipeline monitors CPU, RAM, GPU utilization, and VRAM in real-time.
                </p>
                <p>
                  <span className="font-medium text-white">Storage Hygiene:</span> Transcripts and models stay in your chosen local data folder to keep your C: drive clean.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setHelpOpen(false)}
                className="subtle-button mt-5 px-4 py-2 text-xs font-semibold"
              >
                Close
              </button>
            </section>
          </div>,
          document.body
        )}

      {/* Engine Loading Indicator */}
      {!bootstrap && (
        <div className="pointer-events-none fixed bottom-5 right-5 flex items-center gap-2 rounded-lg border border-[var(--line)] bg-[var(--surface-raised)] px-3 py-2 text-[10px] text-[var(--muted)] shadow-xl">
          <LoaderCircle size={13} className="animate-spin text-[var(--cyan)]" /> Connecting to local engine…
        </div>
      )}
    </div>
  );
}
