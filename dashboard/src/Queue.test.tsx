import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows each claim with its state and decision", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(claims)));
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
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(claims)));
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
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json([claim({ status: "in_progress" })]))
    .mockResolvedValue(Response.json([claim({ status: "decided" })]));
  vi.stubGlobal("fetch", fetchMock);
  render(<Queue />);
  expect(
    await screen.findByText("In progress", { selector: ".chip" }),
  ).toBeDefined();
  await vi.advanceTimersByTimeAsync(2500);
  expect(
    await screen.findByText("Decided", { selector: ".chip" }),
  ).toBeDefined();
  vi.useRealTimers();
});

it("says when the queue cannot be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<Queue />);
  expect(await screen.findByRole("alert")).toBeDefined();
});
