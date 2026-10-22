import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InstructionsPage } from "./InstructionsPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("renders the instructions", async () => {
  const text =
    "You are the agent.\n\n## Steps\n\n1. Read `get_claim`.\n2. **Decide**.";
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(text)));
  render(<InstructionsPage />);
  expect(await screen.findByText("You are the agent.")).toBeDefined();
  expect(screen.getByRole("heading", { name: "Steps" })).toBeDefined();
  expect(screen.getByText("get_claim").tagName).toBe("CODE");
  expect(screen.getByText("Decide").tagName).toBe("STRONG");
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
});

it("renders bullet lists", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("- a\n- b")));
  render(<InstructionsPage />);
  expect(await screen.findAllByRole("listitem")).toHaveLength(2);
});

it("says when the instructions cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 500 })),
  );
  render(<InstructionsPage />);
  expect(await screen.findByRole("alert")).toBeDefined();
});

it("keeps nested bullets inside their item and the numbering going", async () => {
  const text = "1. First\n   - inner\n2. Second";
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(text)));
  const { container } = render(<InstructionsPage />);
  await screen.findByText("First");
  expect(container.querySelectorAll("ol > li")).toHaveLength(2);
  expect(container.querySelectorAll("ol > li > ul > li")).toHaveLength(1);
});

it("starts a list at its own number", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("4. Four")));
  const { container } = render(<InstructionsPage />);
  await screen.findByText("Four");
  expect(container.querySelector("ol")?.getAttribute("start")).toBe("4");
});
