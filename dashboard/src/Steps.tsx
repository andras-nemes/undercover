import type { AgentEvent } from "./api";
import { useApi } from "./useApi";

const KIND_LABELS: Record<string, string> = {
  started: "Started",
  tool_call: "Tool call",
  tool_result: "Result",
  finished: "Finished",
  error: "Error",
};

const always = () => true;
const never = () => false;

function time(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US");
}

export function Steps({
  claimId,
  live,
}: Readonly<{ claimId: string; live: boolean }>) {
  const { data: events } = useApi<AgentEvent[]>(
    `/api/claims/${claimId}/events`,
    live ? always : never,
  );

  return (
    <section className="panel">
      <h2>Agent steps</h2>
      {events?.length === 0 && (
        <p className="note">The agent has not worked on this claim yet.</p>
      )}
      <ol className="steps">
        {events?.map((event, index) => (
          <li key={index} className={event.kind === "error" ? "failed" : ""}>
            <span className="step-kind">
              {KIND_LABELS[event.kind] ?? event.kind}
            </span>
            <span className="step-time mono">{time(event.created_at)}</span>
            <span className="step-text">{event.text}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
