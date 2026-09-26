import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SettingsView } from "./SettingsView";

describe("SettingsView controls", () => {
  it("keeps storage, relaunch, and update controls in settings and invokes the requested actions", async () => {
    const user = userEvent.setup();
    const onRelaunch = vi.fn();
    const onChooseDataDirectory = vi.fn();
    const onCheckForUpdates = vi.fn();
    const onOpenReleasePage = vi.fn();

    render(
      <SettingsView
        onRelaunch={onRelaunch}
        dataDirectory="D:\\JanesCriberData"
        onChooseDataDirectory={onChooseDataDirectory}
        updateStatus={{
          state: "available",
          currentVersion: "1.0.0",
          latestVersion: "1.0.1",
          releaseName: "JanesCriber 1.0.1",
          checkedAt: "15:00:00",
        }}
        onCheckForUpdates={onCheckForUpdates}
        onOpenReleasePage={onOpenReleasePage}
      />
    );

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Choose data folder" }));
    await user.click(screen.getByRole("button", { name: "Relaunch JanesCriber" }));
    await user.click(screen.getByRole("button", { name: "Check for updates" }));
    await user.click(screen.getByRole("button", { name: "Open JanesCriber release page" }));

    expect(onChooseDataDirectory).toHaveBeenCalledOnce();
    expect(onRelaunch).toHaveBeenCalledOnce();
    expect(onCheckForUpdates).toHaveBeenCalledOnce();
    expect(onOpenReleasePage).toHaveBeenCalledOnce();
  });

  it("handles accent and background color presets and reset", async () => {
    const user = userEvent.setup();
    const onAccentColorChange = vi.fn();
    const onBgColorChange = vi.fn();
    const onResetColors = vi.fn();

    render(
      <SettingsView
        onRelaunch={vi.fn()}
        dataDirectory="D:\\JanesCriberData"
        onChooseDataDirectory={vi.fn()}
        updateStatus={{ state: "current", currentVersion: "1.0.0", latestVersion: "1.0.0", checkedAt: "12:00:00" }}
        onCheckForUpdates={vi.fn()}
        onOpenReleasePage={vi.fn()}
        accentColor="#c52b68"
        bgColor="#02000a"
        onAccentColorChange={onAccentColorChange}
        onBgColorChange={onBgColorChange}
        onResetColors={onResetColors}
      />
    );

    expect(screen.getByText("Interface Theme & Color Palette")).toBeInTheDocument();

    // Click an accent preset swatch
    const cyanPreset = screen.getByTitle("Cyber Cyan");
    await user.click(cyanPreset);
    expect(onAccentColorChange).toHaveBeenCalledWith("#06b6d4");

    // Click a background preset swatch
    const navyPreset = screen.getByTitle("Midnight Navy");
    await user.click(navyPreset);
    expect(onBgColorChange).toHaveBeenCalledWith("#0b0f17");

    // Click reset colors
    const resetBtn = screen.getByRole("button", { name: /Reset colors/i });
    await user.click(resetBtn);
    expect(onResetColors).toHaveBeenCalledOnce();
  });

  it("triggers onOpenHelp when the quick guide button is clicked", async () => {
    const user = userEvent.setup();
    const onOpenHelp = vi.fn();

    render(
      <SettingsView
        onRelaunch={vi.fn()}
        dataDirectory="D:\\JanesCriberData"
        onChooseDataDirectory={vi.fn()}
        updateStatus={{ state: "current", currentVersion: "1.0.0", latestVersion: "1.0.0", checkedAt: "12:00:00" }}
        onCheckForUpdates={vi.fn()}
        onOpenReleasePage={vi.fn()}
        onOpenHelp={onOpenHelp}
      />
    );

    const helpBtn = screen.getByRole("button", { name: /Quick guide/i });
    await user.click(helpBtn);
    expect(onOpenHelp).toHaveBeenCalledOnce();
  });
});
