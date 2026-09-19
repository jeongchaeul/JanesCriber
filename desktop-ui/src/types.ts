export type ViewKey = "studio" | "library" | "live" | "hardware" | "console" | "settings";
export type EngineId = "whisper" | "qwen3-asr" | "vosk" | "wav2vec2";

export interface LanguageOption {
  code: string;
  name: string;
}

export interface ModelOption {
  id: string;
  label: string;
}

export interface Bootstrap {
  projectRoot: string;
  transcriptRoot: string;
  cacheRoot: string;
  tempRoot: string;
  hardware: Record<string, string | number | boolean>;
  engines: EngineId[];
  models: Record<EngineId, ModelOption[]>;
  languages: LanguageOption[];
}

export interface TranscriptEntry {
  name: string;
  path: string;
  size: number;
  modified: number;
}

export interface HardwareSnapshot {
  cpuSystemPct: number;
  cpuAppPct: number;
  ramSystemPct: number;
  ramUsedGb: number;
  ramTotalGb: number;
  ramAppMb: number;
  gpuSystemPct: number;
  gpuAppPct: number;
  gpuVramUsedMb: number;
  gpuVramTotalMb: number;
  gpuAppVramMb: number;
  gpuTempC: number;
  gpuEngineName: string;
  gpuName: string;
  gpuBackend: string;
  telemetrySource: string;
  active: boolean;
}

export interface CaptureSource {
  kind: "microphone" | "system" | "application";
  label: string;
  identifier: string | null;
  pid?: number | null;
}

export interface BackendMessage {
  type: "response" | "event";
  id: string;
  ok?: boolean;
  data?: unknown;
  error?: string;
  event?: string;
  [key: string]: unknown;
}

export interface LogLine {
  id: number;
  message: string;
  tone: "normal" | "success" | "warning" | "error";
  at: string;
}
