import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import type { BackendMessage } from "./types";

let sequence = 0;

function nextId(prefix: string): string {
  sequence += 1;
  return prefix + "-" + Date.now().toString(36) + "-" + sequence.toString(36);
}

export async function request<T>(operation: string, payload: Record<string, unknown> = {}): Promise<T> {
  const requestId = nextId("request");
  let unsubscribe: UnlistenFn | undefined;
  const response = new Promise<T>(async (resolve, reject) => {
    unsubscribe = await listen<BackendMessage>("backend-event", (event) => {
      const message = event.payload;
      if (message.type !== "response" || message.id !== requestId) return;
      unsubscribe?.();
      if (message.ok === false) reject(new Error(message.error || "The local engine rejected the request."));
      else resolve(message.data as T);
    });
  });
  try {
    await invoke("backend_request", { requestId, operation, payload });
    return await response;
  } catch (error) {
    unsubscribe?.();
    throw error;
  }
}

export function subscribe(listener: (message: BackendMessage) => void): Promise<UnlistenFn> {
  return listen<BackendMessage>("backend-event", (event) => listener(event.payload));
}

export async function chooseMedia(): Promise<string | null> {
  const value = await open({
    title: "Choose audio or video",
    multiple: false,
    directory: false,
  });
  return typeof value === "string" ? value : null;
}

export async function openManagedPath(path: string): Promise<void> {
  await invoke("open_path", { path });
}

export async function stopBackend(): Promise<void> {
  await invoke("backend_stop");
}

export async function setFrontendPreference(preference: "tauri" | "python"): Promise<void> {
  await invoke("set_frontend_preference", { preference });
}

export async function relaunchLauncher(): Promise<void> {
  await invoke("relaunch_launcher");
}
