export type Status =
  "waiting" | "in_progress" | "awaiting_sign_off" | "decided";
export type Outcome = "approve" | "decline" | "refer";

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

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok)
    throw new Error(`${path} returned ${response.status.toString()}`);
  return (await response.json()) as T;
}

export async function getText(path: string): Promise<string> {
  const response = await fetch(path);
  if (!response.ok)
    throw new Error(`${path} returned ${response.status.toString()}`);
  return response.text();
}
