import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { ClaimSummary } from "./api";
import { Queue } from "./Queue";

function claim(overrides: Partial<ClaimSummary>): ClaimSummary {
  return {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "",
    customer_name: "Maya Patel",
    amount_claimed: 420,
    status: "waiting",
    decision: null,
    payout: null,
    ...overrides,
  };
}

const claims = [
  claim({}),
  claim({
    claim_id: "CLM-1002",
    customer_name: "Tom Becker",
    status: "decided",
    decision: "approve",
    payout: 1250,
  }),
  claim({
    claim_id: "CLM-1003",
    customer_name: "Aiko Tanaka",
    status: "decided",
    decision: "decline",
    payout: 0,
  }),
  claim({ claim_id: "CLM-1004", status: "awaiting_sign_off" }),
];

function stubFetch(
  claimsFn: () => ClaimSummary[] | undefined,
): ReturnType<typeof vi.fn> {
  const mock = vi.fn((path: string) =>
    Promise.resolve(
      path === "/api/runs/latest"
        ? Response.json(null)
        : Response.json(claimsFn()),
    ),
  );
  vi.stubGlobal("fetch", mock);
  return mock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows each claim with its state and decision", async () => {
  stubFetch(() => claims);
  render(<Queue />);
  expect(await screen.findByText("Tom Becker")).toBeDefined();
  expect(screen.getByText("Approved $1,250.00")).toBeDefined();
  expect(screen.getByText("Declined")).toBeDefined();
  expect(
    screen.getByText("Waiting for sign-off", { selector: ".chip" }),
  ).toBeDefined();
  expect(screen.getAllByText("Trip delay")).toHaveLength(4);
});

it("filters the queue by state", async () => {
  stubFetch(() => claims);
  render(<Queue />);
  await screen.findByText("Tom Becker");
  fireEvent.click(screen.getByRole("button", { name: /^Decided/ }));
  expect(screen.queryByText("CLM-1001")).toBeNull();
  expect(screen.getByText("CLM-1002")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: /^All/ }));
  expect(screen.getByText("CLM-1001")).toBeDefined();
});

it("refreshes while a claim is in progress", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let current = [claim({ status: "in_progress" })];
  stubFetch(() => current);
  render(<Queue />);
  expect(
    await screen.findByText("In progress", { selector: ".chip" }),
  ).toBeDefined();
  current = [claim({ status: "decided" })];
  await vi.advanceTimersByTimeAsync(2500);
  expect(
    await screen.findByText("Decided", { selector: ".chip" }),
  ).toBeDefined();
  vi.useRealTimers();
});

it("says when the queue cannot be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<Queue />);
  expect(
    await screen.findByText("The queue could not be loaded."),
  ).toBeDefined();
});

it("keeps refreshing once a run starts filling the queue", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let current = [claim({}), claim({ claim_id: "CLM-1002" })];
  const mock = vi.fn((path: string, init?: RequestInit) => {
    if (path === "/api/runs/latest")
      return Promise.resolve(Response.json(null));
    if (init?.method === "POST") {
      return Promise.resolve(
        Response.json({
          run_id: 1,
          started_at: "2026-10-22T08:00:00+00:00",
          limit: 0,
          status: "running",
          summary: "",
          todos: [],
        }),
      );
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal("fetch", mock);
  render(<Queue />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Run all waiting" }),
  );
  await waitFor(() => {
    expect(mock).toHaveBeenCalledWith("/api/runs", expect.anything());
  });
  current = current.map((c) => ({ ...c, status: "decided" as const }));
  await vi.advanceTimersByTimeAsync(2500);
  await waitFor(() => {
    expect(screen.getAllByText("Decided", { selector: ".chip" })).toHaveLength(
      2,
    );
  });
  vi.useRealTimers();
});
