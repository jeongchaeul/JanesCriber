import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LibraryView } from "./LibraryView";

vi.mock("../bridge", () => ({
  openManagedPath: vi.fn(),
  request: vi.fn(async (method: string) => method === "library_list" ? [] : { content: "" }),
}));

describe("LibraryView layout", () => {
  it("keeps the library viewport fixed and scrolls panel contents internally", async () => {
    const { container } = render(<LibraryView bootstrap={null} refreshKey={0} />);
    const viewport = container.querySelector("section");
    const scrollRegions = container.querySelectorAll(".muted-scroll");

    await waitFor(() => {
      expect(viewport).toHaveClass("flex", "min-h-0", "overflow-hidden");
      expect(scrollRegions).toHaveLength(2);
      scrollRegions.forEach((region) => expect(region).toHaveClass("min-h-0", "flex-1", "overflow-y-auto"));
    });
  });
});
