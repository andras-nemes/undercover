import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { AgentEvent, ClaimDetail } from "./api";
import { ClaimPage } from "./ClaimPage";

const plan = {
  name: "UnderCover Premium",
  trip_cancellation_max: 5000,
  trip_delay_waiting_hours: 6,
  trip_delay_max: 800,
  baggage_delay_waiting_hours: 12,
  baggage_delay_max: 300,
  baggage_max: 1500,
  per_item_limit: 300,
  passport_max: 250,
  emergency_medical_max: 100000,
  deductible: 50,
};

function claim(overrides: Partial<ClaimDetail> = {}): ClaimDetail {
  return {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "Flight home canceled",
    story: "My flight was canceled.",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    amount_claimed: 420,
    items: [
      { description: "Airport hotel", category: "accommodation", amount: 420 },
    ],
    documents: [
      { name: "Hotel receipt", type: "receipt", content: "Paid $245.00." },
    ],
    status: "waiting",
    policy: {
      policy_id: "POL-2001",
      plan: "premium",
      add_ons: ["electronics_plus"],
      purchased_on: "2026-04-22",
      trip: {
        destination: "Rome, Italy",
        departs_on: "2026-06-10",
        returns_on: "2026-06-18",
        trip_cost: 3100,
      },
      travelers: ["Maya Patel"],
      limits: plan,
    },
    customer: {
      customer_id: "CUS-3001",
      name: "Maya Patel",
      previous_claims: [
        {
          claim_id: "CLM-0412",
          filed_on: "2024-08-19",
          claim_type: "baggage_delay",
          summary: "Bag arrived late",
          outcome: "approved",
          amount_paid: 140,
        },
      ],
    },
    decision: null,
    payment: null,
    sign_off: null,
    ...overrides,
  };
}

const approved = {
  decision: "approve" as const,
  payout: 1250,
  reason: "Covered by the wording.",
  policy_section: "Section 3, Trip Delay",
};

const handlers = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
  { handler_id: "HND-02", name: "Marcus Oyelaran", role: "Claims Handler" },
];

interface Server {
  claim: ClaimDetail;
  events: AgentEvent[];
}

function stubServer(server: Server) {
  const mock = vi.fn((path: string, init?: RequestInit) => {
    if (init?.method === "POST") return Promise.resolve(Response.json({}));
    if (path.endsWith("/events"))
      return Promise.resolve(Response.json(server.events));
    if (path === "/api/handlers")
      return Promise.resolve(Response.json(handlers));
    return Promise.resolve(Response.json(server.claim));
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function posts(mock: ReturnType<typeof stubServer>) {
  return mock.mock.calls.filter(([, init]) => init?.method === "POST");
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("shows the claim, its documents, policy and the customer's history", async () => {
  stubServer({ claim: claim(), events: [] });
  render(<ClaimPage id="CLM-1001" />);
  expect(await screen.findByText("My flight was canceled.")).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("Hotel receipt")).toBeDefined();
  expect(screen.getByText("Paid $245.00.")).toBeDefined();
  expect(screen.getByText(/UnderCover Premium/)).toBeDefined();
  expect(screen.getByText(/Bag arrived late/)).toBeDefined();
  expect(
    await screen.findByText("The agent has not worked on this claim yet."),
  ).toBeDefined();
});

it("shows the decision with its reason and policy section", async () => {
  const detail = claim({
    status: "decided",
    decision: { ...approved, payout: 420 },
    payment: { amount: 420, paid_at: "2026-10-22T08:00:00+00:00" },
  });
  stubServer({ claim: detail, events: [] });
  render(<ClaimPage id="CLM-1001" />);
  expect(await screen.findByText("Approved")).toBeDefined();
  expect(screen.getByText("Covered by the wording.")).toBeDefined();
  expect(screen.getByText("Policy: Section 3, Trip Delay")).toBeDefined();
  expect(screen.getAllByText("$420.00").length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "Sign off and pay" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
});

it("shows a decline without a payout", async () => {
  const detail = claim({
    status: "decided",
    decision: { ...approved, decision: "decline", payout: 0 },
  });
  stubServer({ claim: detail, events: [] });
  render(<ClaimPage id="CLM-1001" />);
  expect(await screen.findByText("Declined")).toBeDefined();
});

it("runs the agent on a waiting claim", async () => {
  const server = { claim: claim(), events: [] };
  const mock = stubServer(server);
  render(<ClaimPage id="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  await waitFor(() => {
    expect(posts(mock)).toHaveLength(1);
  });
  expect(posts(mock)[0]?.[0]).toBe("/api/claims/CLM-1001/run");
});

it("shows why the agent could not be run", async () => {
  const mock = vi.fn((path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const failure = { detail: "Claim CLM-1001 is not waiting" };
      return Promise.resolve(Response.json(failure, { status: 409 }));
    }
    const body = path.endsWith("/events") ? [] : claim();
    return Promise.resolve(Response.json(body));
  });
  vi.stubGlobal("fetch", mock);
  render(<ClaimPage id="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect(await screen.findByText(/not waiting/)).toBeDefined();
});

it("signs off a claim as the chosen handler", async () => {
  const detail = claim({ status: "awaiting_sign_off", decision: approved });
  const mock = stubServer({ claim: detail, events: [] });
  render(<ClaimPage id="CLM-1001" />);
  const button = await screen.findByRole("button", {
    name: "Sign off and pay",
  });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "HND-02" },
  });
  expect((button as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(button);
  await waitFor(() => {
    expect(posts(mock)).toHaveLength(1);
  });
  const [path, init] = posts(mock)[0] ?? [];
  expect(path).toBe("/api/claims/CLM-1001/sign-off");
  expect(init?.body).toBe(JSON.stringify({ handler_id: "HND-02" }));
});

it("shows who signed off a paid claim", async () => {
  const detail = claim({
    status: "decided",
    decision: approved,
    payment: { amount: 1250, paid_at: "2026-10-22T08:00:00+00:00" },
    sign_off: {
      handler_id: "HND-01",
      handler_name: "Dana Whitfield",
      signed_at: "2026-10-22T08:00:00+00:00",
    },
  });
  stubServer({ claim: detail, events: [] });
  render(<ClaimPage id="CLM-1001" />);
  expect(
    await screen.findByText(/after sign-off by Dana Whitfield/),
  ).toBeDefined();
});

it("shows a failed sign-off", async () => {
  const detail = claim({ status: "awaiting_sign_off", decision: approved });
  const mock = vi.fn((path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      return Promise.resolve(Response.json({ detail: "No." }, { status: 409 }));
    }
    if (path.endsWith("/events")) return Promise.resolve(Response.json([]));
    return Promise.resolve(
      Response.json(path === "/api/handlers" ? handlers : detail),
    );
  });
  vi.stubGlobal("fetch", mock);
  render(<ClaimPage id="CLM-1001" />);
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
  expect(await screen.findByText(/No\./)).toBeDefined();
});

it("polls the claim and its steps while the agent works, then stops", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const server: Server = {
    claim: claim({ status: "in_progress" }),
    events: [
      {
        kind: "started",
        text: "Started on CLM-1001",
        created_at: "2026-10-22T08:00:00+00:00",
      },
    ],
  };
  const mock = stubServer(server);
  render(<ClaimPage id="CLM-1001" />);
  expect(await screen.findByText("Started on CLM-1001")).toBeDefined();

  server.events = [
    ...server.events,
    {
      kind: "tool_call",
      text: "get_claim {}",
      created_at: "2026-10-22T08:00:01+00:00",
    },
  ];
  await vi.advanceTimersByTimeAsync(2500);
  expect(await screen.findByText("get_claim {}")).toBeDefined();

  server.claim = claim({ status: "decided", decision: approved });
  server.events = [
    ...server.events,
    {
      kind: "error",
      text: "The agent stopped: boom",
      created_at: "2026-10-22T08:00:02+00:00",
    },
  ];
  await vi.advanceTimersByTimeAsync(2500);
  expect(await screen.findByText("The agent stopped: boom")).toBeDefined();

  await vi.advanceTimersByTimeAsync(3000);
  const calls = mock.mock.calls.length;
  await vi.advanceTimersByTimeAsync(6000);
  expect(mock.mock.calls).toHaveLength(calls);
});

it("says when the claim cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 404 })),
  );
  render(<ClaimPage id="CLM-9999" />);
  expect(await screen.findByRole("alert")).toBeDefined();
});
