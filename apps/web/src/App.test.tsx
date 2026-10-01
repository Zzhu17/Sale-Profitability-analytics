import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("states the D0 boundary", () => {
    render(<App />);
    expect(screen.getByText("Pending real anonymized data")).toBeInTheDocument();
    expect(screen.getByText(/No model metrics or business outcomes/)).toBeInTheDocument();
  });
});
