import type { UpdateStatus } from "./types";

const RELEASES_API = "https://api.github.com/repos/janecerys/JanesCriber/releases/latest";

type JsonObject = Record<string, unknown>;

function objectValue(value: unknown): JsonObject | null {
  return typeof value === "object" && value !== null ? value as JsonObject : null;
}

function textValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function versionParts(value: string): [number, number, number] | null {
  const match = value.trim().replace(/^v/i, "").match(/^(\d+)\.(\d+)\.(\d+)$/);
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function compareVersions(left: string, right: string): number {
  const leftParts = versionParts(left);
  const rightParts = versionParts(right);
  if (!leftParts || !rightParts) return 0;
  for (let index = 0; index < leftParts.length; index += 1) {
    if (leftParts[index] !== rightParts[index]) return leftParts[index] > rightParts[index] ? 1 : -1;
  }
  return 0;
}

function hasInstallerAsset(value: unknown): boolean {
  if (!Array.isArray(value)) return false;
  return value.some((asset) => {
    const item = objectValue(asset);
    const name = textValue(item?.name);
    return Boolean(name?.toLowerCase().endsWith("-setup.exe"));
  });
}

function checkedAt(): string {
  return new Date().toLocaleTimeString();
}

export async function checkForUpdates(currentVersion: string): Promise<UpdateStatus> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 6500);
  try {
    const response = await fetch(RELEASES_API, {
      headers: { Accept: "application/vnd.github+json" },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`GitHub returned ${response.status}.`);
    const release = objectValue(await response.json());
    const tag = textValue(release?.tag_name);
    const releaseName = textValue(release?.name) || tag;
    const releaseUrl = textValue(release?.html_url);
    const isDraft = release?.draft === true;
    const isPrerelease = release?.prerelease === true;
    const isOfficialRelease = releaseUrl?.startsWith("https://github.com/janecerys/JanesCriber/releases/") ?? false;
    if (!tag || !versionParts(tag) || isDraft || isPrerelease || !isOfficialRelease) {
      throw new Error("The latest release metadata was not valid.");
    }
    if (compareVersions(tag, currentVersion) <= 0) {
      return { state: "current", currentVersion, latestVersion: tag.replace(/^v/i, ""), checkedAt: checkedAt() };
    }
    if (!hasInstallerAsset(release?.assets)) {
      return { state: "not-ready", currentVersion, latestVersion: tag.replace(/^v/i, ""), checkedAt: checkedAt() };
    }
    return { state: "available", currentVersion, latestVersion: tag.replace(/^v/i, ""), releaseName: releaseName || tag, checkedAt: checkedAt() };
  } catch {
    return { state: "offline", currentVersion, message: "Could not reach the official GitHub Releases page." };
  } finally {
    window.clearTimeout(timeout);
  }
}
