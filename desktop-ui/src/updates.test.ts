import { beforeEach, describe, expect, it, vi } from "vitest";
import { checkForUpdates } from "./updates";

describe("release update checker", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("reports the installed version as current when the latest release is not newer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        tag_name: "v1.0.0",
        name: "JanesCriber 1.0.0",
        html_url: "https://github.com/janecerys/JanesCriber/releases/tag/v1.0.0",
        draft: false,
        prerelease: false,
        assets: [{ name: "JanesCriber-1.0.0-Setup.exe" }],
      }),
    }));

    const result = await checkForUpdates("1.0.0");
    expect(result.state).toBe("current");
  });

  it("only offers an update when an official release has an installer asset", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        tag_name: "v1.1.0",
        name: "JanesCriber 1.1.0",
        html_url: "https://github.com/janecerys/JanesCriber/releases/tag/v1.1.0",
        draft: false,
        prerelease: false,
        assets: [{ name: "JanesCriber-1.1.0-Setup.exe" }],
      }),
    }));

    const result = await checkForUpdates("1.0.0");
    expect(result).toMatchObject({ state: "available", latestVersion: "1.1.0" });
  });
});
