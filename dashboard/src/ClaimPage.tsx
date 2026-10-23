import { useState } from "react";
import { post, type ClaimDetail } from "./api";
import { ClaimDetails } from "./ClaimDetails";
import { DecisionPanel } from "./DecisionPanel";
import { StatusChip } from "./Queue";
import { ReadsPanel } from "./ReadsPanel";
import { Steps } from "./Steps";
import { useApi } from "./useApi";

function inProgress(claim: ClaimDetail): boolean {
  return claim.status === "in_progress";
}

export function ClaimPage({ id }: Readonly<{ id: string }>) {
  const {
    data: claim,
    error,
    reload,
  } = useApi<ClaimDetail>(`/api/claims/${id}`, inProgress);
  const [runError, setRunError] = useState<string | null>(null);

  const run = () => {
    post(`/api/claims/${id}/run`)
      .then(reload)
      .catch((failure: unknown) => {
        setRunError(String(failure));
      });
  };

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      {error && <p role="alert">This claim could not be loaded.</p>}
      {claim && (
        <>
          <h1>
            <span className="mono">{claim.claim_id}</span> {claim.summary}
          </h1>
          <div className="actions">
            <StatusChip status={claim.status} />
            {claim.status === "waiting" && (
              <button className="primary" onClick={run}>
                Run agent
              </button>
            )}
            {runError && <span role="alert">{runError}</span>}
          </div>
          <div className="claim-grid">
            <div className="stack">
              <DecisionPanel claim={claim} onChange={reload} />
              <Steps claimId={id} live={claim.status === "in_progress"} />
              <ReadsPanel claim={claim} />
            </div>
            <div className="stack">
              <ClaimDetails claim={claim} />
            </div>
          </div>
        </>
      )}
    </>
  );
}
