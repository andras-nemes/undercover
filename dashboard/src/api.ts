export type Status =
  "waiting" | "in_progress" | "awaiting_sign_off" | "decided" | "needs_handler";
export type Outcome = "approve" | "decline" | "refer";
export type TodoStatus = "todo" | "in_progress" | "done" | "left_for_handler";
export type RunStatus = "running" | "finished" | "failed";
export type DocumentName = "wording" | "manual";

export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  summary: string;
  customer_name: string;
  amount_claimed: number;
  status: Status;
  decision: Outcome | null;
  payout: number | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Plan {
  name: string;
  trip_cancellation_max: number;
  trip_delay_waiting_hours: number;
  trip_delay_max: number;
  baggage_delay_waiting_hours: number;
  baggage_delay_max: number;
  baggage_max: number;
  per_item_limit: number;
  passport_max: number;
  emergency_medical_max: number;
  deductible: number;
}

export interface Policy {
  policy_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  limits: Plan;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Decision {
  decision: Outcome;
  payout: number;
  reason: string;
  policy_section: string;
}

export interface Read {
  document: DocumentName;
  section: number;
  title: string;
}

export interface Todo {
  content: string;
  status: TodoStatus;
}

export interface Run {
  run_id: number;
  started_at: string;
  limit: number;
  status: RunStatus;
  summary: string;
  todos: Todo[];
}

export interface ClaimDetail {
  claim_id: string;
  claim_type: string;
  summary: string;
  story: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  amount_claimed: number;
  items: Item[];
  documents: ClaimDocument[];
  status: Status;
  policy: Policy;
  customer: {
    customer_id: string;
    name: string;
    previous_claims: PreviousClaim[];
  };
  decision: Decision | null;
  payment: { amount: number; paid_at: string } | null;
  sign_off: {
    handler_id: string;
    handler_name: string;
    signed_at: string;
  } | null;
  reads: Read[];
}

export interface AgentEvent {
  kind: string;
  text: string;
  created_at: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status.toString()}`);
  }
  return (await response.json()) as T;
}

export async function getText(path: string): Promise<string> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status.toString()}`);
  }
  return response.text();
}

export async function post(path: string, body?: object): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body && JSON.stringify(body),
  });
  if (!response.ok) {
    const failure = (await response.json()) as { detail: string };
    throw new Error(failure.detail);
  }
}
