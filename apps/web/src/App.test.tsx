import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("shows the import and Gate 1 boundaries", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /review source data/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
    expect(screen.getByText(/Gate 1 controls real-data mapping activation/)).toBeInTheDocument();
    expect(screen.getByText(/No model metrics or business outcomes/)).toBeInTheDocument();
  });
});
