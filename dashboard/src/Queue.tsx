import { useEffect, useState } from "react";
import type { ClaimSummary, Status } from "./api";
import { OUTCOME_LABELS, STATUS_LABELS, label, money } from "./format";
import { RunPanel } from "./RunPanel";
import { useApi } from "./useApi";

const STATUSES = Object.keys(STATUS_LABELS) as Status[];

function anyInProgress(claims: ClaimSummary[]): boolean {
  return claims.some((claim) => claim.status === "in_progress");
}

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  return <span className={`chip chip-${status}`}>{STATUS_LABELS[status]}</span>;
}

function decisionText(claim: ClaimSummary): string {
  if (claim.decision === null) return "";
  const outcome = OUTCOME_LABELS[claim.decision];
  return claim.decision === "approve" && claim.payout !== null
    ? `${outcome} ${money(claim.payout)}`
    : outcome;
}

export function Queue() {
  const {
    data: claims,
    error,
    reload,
  } = useApi<ClaimSummary[]>("/api/claims", anyInProgress);
  const [filter, setFilter] = useState<Status | "all">("all");
  const [running, setRunning] = useState(false);
  const active =
    running &&
    (claims?.some(
      (c) => c.status === "waiting" || c.status === "in_progress",
    ) ??
      false);

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(reload, 2000);
    return () => {
      window.clearInterval(timer);
    };
  }, [active, reload]);

  const onStarted = () => {
    setRunning(true);
    reload();
  };

  const count = (status: Status) =>
    (claims ?? []).filter((c) => c.status === status).length;
  const shown =
    claims &&
    (filter === "all" ? claims : claims.filter((c) => c.status === filter));

  return (
    <>
      <h1>Claims queue</h1>
      <RunPanel onStarted={onStarted} />
      {error && <p role="alert">The queue could not be loaded.</p>}
      {!error && !claims && <p>Loading the queue</p>}
      {!error && claims && shown && (
        <>
          <div className="filters">
            <button
              aria-pressed={filter === "all"}
              onClick={() => {
                setFilter("all");
              }}
            >
              All <span className="mono">{claims.length}</span>
            </button>
            {STATUSES.map((status) => (
              <button
                key={status}
                aria-pressed={filter === status}
                onClick={() => {
                  setFilter(status);
                }}
              >
                {STATUS_LABELS[status]}{" "}
                <span className="mono">{count(status)}</span>
              </button>
            ))}
          </div>
          <section className="panel table-panel">
            <table>
              <thead>
                <tr>
                  <th scope="col">Claim</th>
                  <th scope="col">Type</th>
                  <th scope="col">Customer</th>
                  <th scope="col" className="num">
                    Claimed
                  </th>
                  <th scope="col">State</th>
                  <th scope="col">Decision</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((claim) => (
                  <tr key={claim.claim_id}>
                    <td className="mono">
                      <a href={`#/claims/${claim.claim_id}`}>
                        {claim.claim_id}
                      </a>
                    </td>
                    <td>{label(claim.claim_type)}</td>
                    <td>{claim.customer_name}</td>
                    <td className="mono num">{money(claim.amount_claimed)}</td>
                    <td>
                      <StatusChip status={claim.status} />
                    </td>
                    <td>{decisionText(claim)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </>
  );
}
