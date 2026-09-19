import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LanguagePicker } from "./LanguagePicker";

describe("LanguagePicker", () => {
  it("searches and applies a selected language without hiding the code", () => {
    const onChange = vi.fn();
    render(<LanguagePicker options={[{ code: "en", name: "English (Global)" }, { code: "tl", name: "Tagalog / Filipino (Taglish)" }]} value={[]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Choose languages…" }));
    fireEvent.change(screen.getByPlaceholderText("Search language, native name, or code…"), { target: { value: "tagalog" } });
    fireEvent.click(screen.getByRole("button", { name: /Tagalog \/ Filipino/ }));
    expect(screen.getByText("1/8 selected")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Apply selection" }));
    expect(onChange).toHaveBeenCalledWith(["tl"]);
  });
});
