import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "./Sidebar";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("Sidebar component", () => {
  it("renders navigation items and fires onChange on item click", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    const onChange = vi.fn();
    const onToggle = vi.fn();

    await act(async () => {
      root.render(
        <Sidebar
          activeView="studio"
          collapsed={false}
          onChange={onChange}
          onToggle={onToggle}
        />
      );
    });

    const nav = container.querySelector("nav");
    expect(nav).not.toBeNull();

    const viewButtons = container.querySelectorAll("nav button:not([aria-label*='sidebar'])");
    expect(viewButtons.length).toBe(6);

    // Click Library button
    const libraryBtn = Array.from(viewButtons).find((b) => b.textContent?.includes("Transcript Library")) as HTMLButtonElement | undefined;
    expect(libraryBtn).toBeDefined();

    await act(async () => {
      libraryBtn?.click();
    });
    expect(onChange).toHaveBeenCalledWith("library");

    // Click collapse toggle button
    const toggleBtn = container.querySelector('button[aria-label="Collapse sidebar"]');
    expect(toggleBtn).not.toBeNull();
    await act(async () => {
      (toggleBtn as HTMLButtonElement)?.click();
    });
    expect(onToggle).toHaveBeenCalled();

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  it("renders correctly in collapsed mode", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <Sidebar
          activeView="studio"
          collapsed={true}
          onChange={vi.fn()}
          onToggle={vi.fn()}
        />
      );
    });

    const aside = container.querySelector("aside");
    expect(aside?.getAttribute("data-collapsed")).toBe("true");

    const expandBtn = container.querySelector('button[aria-label="Expand sidebar"]');
    expect(expandBtn).not.toBeNull();

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});
