import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Run } from "./api";
import { RunPanel } from "./RunPanel";

function run(overrides: Partial<Run> = {}): Run {
  return {
    run_id: 1,
    started_at: "2026-10-22T08:00:00+00:00",
    limit: 0,
    status: "running",
    summary: "",
    todos: [],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("says when no run has started yet", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(null)));
  render(<RunPanel onStarted={() => undefined} />);
  expect(await screen.findByText("No run has started yet.")).toBeDefined();
});

it("renders a to-do item in each status with its chip", async () => {
  const data = run({
    todos: [
      { content: "CLM-1001 trip_delay Maya Patel", status: "todo" },
      { content: "CLM-1002 baggage Tom Becker", status: "in_progress" },
      { content: "CLM-1003 passport Oliver Grant", status: "done" },
      { content: "CLM-1004 baggage Dana Ruiz", status: "left_for_handler" },
    ],
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(data)));
  render(<RunPanel onStarted={() => undefined} />);
  expect(await screen.findByText("To do")).toBeDefined();
  expect(screen.getByText("In progress", { selector: ".chip" })).toBeDefined();
  expect(screen.getByText("Done")).toBeDefined();
  expect(
    screen.getByText("Left for a handler", { selector: ".chip" }),
  ).toBeDefined();
  expect(screen.getByText("CLM-1001 trip_delay Maya Patel")).toBeDefined();
});

it("shows the summary once the run is finished", async () => {
  const data = run({ status: "finished", summary: "Five claims worked." });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(data)));
  render(<RunPanel onStarted={() => undefined} />);
  expect(await screen.findByText("Five claims worked.")).toBeDefined();
});

it("polls while the run is running and stops once it finishes", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const mock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(run({ status: "running" })))
    .mockResolvedValue(
      Response.json(run({ status: "finished", summary: "Done." })),
    );
  vi.stubGlobal("fetch", mock);
  render(<RunPanel onStarted={() => undefined} />);
  await screen.findByText("Running");
  await vi.advanceTimersByTimeAsync(2500);
  expect(await screen.findByText("Done.")).toBeDefined();
  const calls = mock.mock.calls.length;
  await vi.advanceTimersByTimeAsync(6000);
  expect(mock.mock.calls).toHaveLength(calls);
});

it("posts a limit of 0 for 'Run all waiting'", async () => {
  const mock = vi.fn((path: string, init?: RequestInit) =>
    Promise.resolve(
      init?.method === "POST" ? Response.json(run()) : Response.json(null),
    ),
  );
  vi.stubGlobal("fetch", mock);
  const onStarted = vi.fn();
  render(<RunPanel onStarted={onStarted} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Run all waiting" }),
  );
  await waitFor(() => {
    expect(onStarted).toHaveBeenCalled();
  });
  const call = mock.mock.calls.find(([path]) => path === "/api/runs");
  expect(call?.[1]?.body).toBe(JSON.stringify({ limit: 0 }));
});

it("posts the trial field's number for 'Run a trial'", async () => {
  const mock = vi.fn((path: string, init?: RequestInit) =>
    Promise.resolve(
      init?.method === "POST" ? Response.json(run()) : Response.json(null),
    ),
  );
  vi.stubGlobal("fetch", mock);
  render(<RunPanel onStarted={() => undefined} />);
  const field = await screen.findByRole("spinbutton");
  fireEvent.change(field, { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Run a trial" }));
  await waitFor(() => {
    const call = mock.mock.calls.find(([path]) => path === "/api/runs");
    expect(call?.[1]?.body).toBe(JSON.stringify({ limit: 3 }));
  });
});

it("shows why a run could not be started", async () => {
  const mock = vi.fn((path: string, init?: RequestInit) =>
    Promise.resolve(
      init?.method === "POST"
        ? Response.json({ detail: "A run is already going" }, { status: 409 })
        : Response.json(null),
    ),
  );
  vi.stubGlobal("fetch", mock);
  render(<RunPanel onStarted={() => undefined} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Run all waiting" }),
  );
  expect(await screen.findByText(/already going/)).toBeDefined();
});
