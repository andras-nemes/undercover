import { useState } from "react";
import { post, type ClaimDetail, type Handler } from "./api";
import { OUTCOME_LABELS, money } from "./format";
import { useApi } from "./useApi";

function SignOffForm({
  claimId,
  onDone,
}: Readonly<{ claimId: string; onDone: () => void }>) {
  const { data: handlers } = useApi<Handler[]>("/api/handlers");
  const [handlerId, setHandlerId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const signOff = () => {
    post(`/api/claims/${claimId}/sign-off`, { handler_id: handlerId })
      .then(onDone)
      .catch((failure: unknown) => {
        setError(String(failure));
      });
  };

  return (
    <div className="sign-off">
      <p>
        This payout is over the limit. A handler has to sign off before it is
        paid.
      </p>
      <label>
        Handler{" "}
        <select
          value={handlerId}
          onChange={(event) => {
            setHandlerId(event.target.value);
          }}
        >
          <option value="">Choose a handler</option>
          {handlers?.map((handler) => (
            <option key={handler.handler_id} value={handler.handler_id}>
              {handler.name}
            </option>
          ))}
        </select>
      </label>{" "}
      <button className="primary" disabled={handlerId === ""} onClick={signOff}>
        Sign off and pay
      </button>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

export function DecisionPanel({
  claim,
  onChange,
}: Readonly<{ claim: ClaimDetail; onChange: () => void }>) {
  const { decision, payment, sign_off: signOff } = claim;
  if (!decision) return null;

  return (
    <section className="panel">
      <h2>Decision</h2>
      <p className="outcome">
        {OUTCOME_LABELS[decision.decision]}
        {decision.decision === "approve" && (
          <span className="mono"> {money(decision.payout)}</span>
        )}
      </p>
      <p>{decision.reason}</p>
      <p className="note">Policy: {decision.policy_section}</p>
      {payment && (
        <p>
          Paid <span className="mono">{money(payment.amount)}</span>
          {signOff && <> after sign-off by {signOff.handler_name}</>}.
        </p>
      )}
      {claim.status === "awaiting_sign_off" && (
        <SignOffForm claimId={claim.claim_id} onDone={onChange} />
      )}
    </section>
  );
}
