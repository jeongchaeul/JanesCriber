import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SettingsView } from "./SettingsView";

describe("SettingsView interface controls", () => {
  it("keeps launcher controls in settings and invokes the requested actions", async () => {
    const user = userEvent.setup();
    const onSelectInterface = vi.fn();
    const onRelaunch = vi.fn();

    render(<SettingsView onSelectInterface={onSelectInterface} onRelaunch={onRelaunch} />);

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use Main UI next launch" }));
    await user.click(screen.getByRole("button", { name: "Use Legacy Python next launch" }));
    await user.click(screen.getByRole("button", { name: "Relaunch JanesCriber" }));

    expect(onSelectInterface).toHaveBeenNthCalledWith(1, "tauri", "Main UI");
    expect(onSelectInterface).toHaveBeenNthCalledWith(2, "python", "Legacy Python UI");
    expect(onRelaunch).toHaveBeenCalledOnce();
  });
});
