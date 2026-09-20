import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SettingsView } from "./SettingsView";

describe("SettingsView interface controls", () => {
  it("keeps launcher controls in settings and invokes the requested actions", async () => {
    const user = userEvent.setup();
    const onSelectInterface = vi.fn();
    const onRelaunch = vi.fn();
    const onChooseDataDirectory = vi.fn();
    const onCheckForUpdates = vi.fn();
    const onOpenReleasePage = vi.fn();

    render(<SettingsView onSelectInterface={onSelectInterface} onRelaunch={onRelaunch} dataDirectory="D:\\JanesCriberData" onChooseDataDirectory={onChooseDataDirectory} updateStatus={{ state: "available", currentVersion: "1.0.0", latestVersion: "1.0.1", releaseName: "JanesCriber 1.0.1", checkedAt: "15:00:00" }} onCheckForUpdates={onCheckForUpdates} onOpenReleasePage={onOpenReleasePage} />);

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use Main UI next launch" }));
    await user.click(screen.getByRole("button", { name: "Use Legacy Python next launch" }));
    await user.click(screen.getByRole("button", { name: "Relaunch JanesCriber" }));
    await user.click(screen.getByRole("button", { name: "Choose data folder" }));
    await user.click(screen.getByRole("button", { name: "Check for updates" }));
    await user.click(screen.getByRole("button", { name: "Open JanesCriber release page" }));

    expect(onSelectInterface).toHaveBeenNthCalledWith(1, "tauri", "Main UI");
    expect(onSelectInterface).toHaveBeenNthCalledWith(2, "python", "Legacy Python UI");
    expect(onRelaunch).toHaveBeenCalledOnce();
    expect(onChooseDataDirectory).toHaveBeenCalledOnce();
    expect(onCheckForUpdates).toHaveBeenCalledOnce();
    expect(onOpenReleasePage).toHaveBeenCalledOnce();
  });
});
