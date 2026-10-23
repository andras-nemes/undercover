import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InstructionsPage } from "./InstructionsPage";

function stubInstructions(
  texts: Partial<Record<"queue" | "claim", string>> = {},
  status = 200,
) {
  const queue = texts.queue ?? "You run the queue.";
  const claim = texts.claim ?? "You are the agent.";
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string) =>
      Promise.resolve(
        new Response(path === "/api/instructions/queue" ? queue : claim, {
          status,
        }),
      ),
    ),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("renders both sets of instructions", async () => {
  stubInstructions({
    queue: "Work the queue.\n\n## Order\n\n- oldest first",
    claim:
      "You are the agent.\n\n## Steps\n\n1. Read `get_claim`.\n2. **Decide**.",
  });
  render(<InstructionsPage />);
  expect(
    screen.getByRole("heading", { name: "Running the queue" }),
  ).toBeDefined();
  expect(
    screen.getByRole("heading", { name: "Working a claim" }),
  ).toBeDefined();
  expect(await screen.findByText("Work the queue.")).toBeDefined();
  expect(await screen.findByText("You are the agent.")).toBeDefined();
  expect(screen.getByRole("heading", { name: "Steps" })).toBeDefined();
  expect(screen.getByText("get_claim").tagName).toBe("CODE");
  expect(screen.getByText("Decide").tagName).toBe("STRONG");
});

it("renders bullet lists", async () => {
  stubInstructions({ claim: "- a\n- b" });
  render(<InstructionsPage />);
  expect(await screen.findAllByRole("listitem")).toHaveLength(2);
});

it("says when the instructions cannot be loaded", async () => {
  stubInstructions({}, 500);
  render(<InstructionsPage />);
  expect(await screen.findByRole("alert")).toBeDefined();
});

it("keeps nested bullets inside their item and the numbering going", async () => {
  stubInstructions({ claim: "1. First\n   - inner\n2. Second" });
  const { container } = render(<InstructionsPage />);
  await screen.findByText("First");
  expect(container.querySelectorAll("ol > li")).toHaveLength(2);
  expect(container.querySelectorAll("ol > li > ul > li")).toHaveLength(1);
});

it("starts a list at its own number", async () => {
  stubInstructions({ claim: "4. Four" });
  const { container } = render(<InstructionsPage />);
  await screen.findByText("Four");
  expect(container.querySelector("ol")?.getAttribute("start")).toBe("4");
});
