import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { HardwareView } from "./HardwareView";
import type { Bootstrap } from "../types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../bridge", () => ({
  request: vi.fn().mockResolvedValue({
    cpuSystemPct: 15.2,
    cpuAppPct: 3.1,
    ramSystemPct: 45.0,
    ramUsedGb: 14.5,
    ramTotalGb: 32.0,
    ramAppMb: 250,
    gpuSystemPct: 10.0,
    gpuAppPct: 0.0,
    gpuVramUsedMb: 1200,
    gpuVramTotalMb: 8192,
    gpuAppVramMb: 0,
    gpuTempC: 45,
    gpuName: "NVIDIA GeForce RTX 5060",
    gpuBackend: "NVIDIA CUDA / FP16",
    telemetrySource: "nvml",
    active: false,
  }),
}));

describe("HardwareView component", () => {
  const mockBootstrap: Bootstrap = {
    projectRoot: "D:\\JanesCriber",
    transcriptRoot: "D:\\JanesCriber\\Transcripts",
    cacheRoot: "D:\\JanesCriber\\.cache",
    tempRoot: "D:\\JanesCriber\\temp",
    hardware: {
      cpu: "AMD Ryzen 5 5600G with Radeon Graphics",
      cores: "12",
      device: "cuda",
      accelerator: "NVIDIA CUDA / FP16",
      gpu: "NVIDIA GeForce RTX 5060",
      runtime: "12.8",
      reason: "NVIDIA CUDA is available.",
      torch_version: "2.7.1+cu128",
      cuda_runtime: "CUDA 12.8",
    },
    engines: ["whisper", "vosk"],
    outputFormats: [{ id: "txt", label: "Plain text" }],
    models: {
      whisper: [{ id: "turbo", label: "Turbo" }],
      vosk: [{ id: "en-us-small", label: "English" }],
      "qwen3-asr": [],
      wav2vec2: [],
    },
    languages: [{ code: "en", name: "English" }],
  };

  it("renders detected hardware and pipeline tracking", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <HardwareView
          bootstrap={mockBootstrap}
          active={false}
          visible={true}
          progress={0.5}
          progressMessage="Transcribing speech..."
        />
      );
    });

    // Check CPU info
    expect(container.textContent).toContain("AMD Ryzen 5 5600G with Radeon Graphics");
    expect(container.textContent).toContain("12 logical cores");

    // Check Pipeline stages
    expect(container.textContent).toContain("Transcription pipeline tracker");
    expect(container.textContent).toContain("Media input");
    expect(container.textContent).toContain("Audio extraction");
    expect(container.textContent).toContain("Model & accelerator");
    expect(container.textContent).toContain("ASR transcription");

    // Check progress
    expect(container.textContent).toContain("050%");

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});
