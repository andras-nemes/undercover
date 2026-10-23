import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import type { ClaimSummary } from "./api";

const claims: ClaimSummary[] = [
  {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "Flight canceled",
    customer_name: "Maya Patel",
    amount_claimed: 420,
    status: "waiting",
    decision: null,
    payout: null,
  },
];

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string) =>
      Promise.resolve(
        path === "/api/instructions/claim"
          ? new Response("You are the agent.\n\n## Steps\n\n- one")
          : Response.json(claims),
      ),
    ),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

it("shows the queue by default", async () => {
  stubFetch();
  render(<App />);
  expect(await screen.findByText("Maya Patel")).toBeDefined();
  expect(screen.getByRole("heading", { name: "Claims queue" })).toBeDefined();
});

it("shows the instructions at their address", async () => {
  stubFetch();
  window.location.hash = "#/instructions";
  render(<App />);
  expect(await screen.findByText("You are the agent.")).toBeDefined();
});

it("shows a claim at its address", () => {
  stubFetch();
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(screen.getByRole("link", { name: "Back to the queue" })).toBeDefined();
});

it("says when a page does not exist", () => {
  stubFetch();
  window.location.hash = "#/nowhere";
  render(<App />);
  expect(screen.getByText("That page does not exist.")).toBeDefined();
});
