import type { ClaimDetail } from "./api";
import { label, money } from "./format";

export function ClaimDetails({ claim }: Readonly<{ claim: ClaimDetail }>) {
  const { policy, customer } = claim;
  return (
    <>
      <section className="panel">
        <h2>The claim</h2>
        <p className="note">
          {label(claim.claim_type)}, incident on{" "}
          <span className="mono">{claim.incident_date}</span> in{" "}
          {claim.incident_location}, filed on{" "}
          <span className="mono">{claim.submitted_on}</span> by {customer.name}
        </p>
        <p>{claim.story}</p>
        <h3>Items claimed</h3>
        <table>
          <tbody>
            {claim.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td>{label(item.category)}</td>
                <td className="mono num">{money(item.amount)}</td>
              </tr>
            ))}
            <tr>
              <th scope="row">Total claimed</th>
              <td />
              <td className="mono num">{money(claim.amount_claimed)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>Documents</h2>
        {claim.documents.map((document) => (
          <div key={document.name} className="document">
            <h3>
              {document.name}{" "}
              <span className="note">{label(document.type)}</span>
            </h3>
            <p>{document.content}</p>
          </div>
        ))}
      </section>

      <section className="panel">
        <h2>Policy</h2>
        <p>
          <span className="mono">{policy.policy_id}</span>, {policy.limits.name}
          {policy.add_ons.length > 0 &&
            `, with ${policy.add_ons.map(label).join(", ").toLowerCase()}`}
        </p>
        <p className="note">
          Bought on <span className="mono">{policy.purchased_on}</span>. Trip to{" "}
          {policy.trip.destination} from{" "}
          <span className="mono">{policy.trip.departs_on}</span> to{" "}
          <span className="mono">{policy.trip.returns_on}</span>, costing{" "}
          {money(policy.trip.trip_cost)}. Travelers:{" "}
          {policy.travelers.join(", ")}.
        </p>
        <h3>{customer.name}&apos;s earlier claims</h3>
        {customer.previous_claims.length === 0 && (
          <p className="note">No earlier claims.</p>
        )}
        <ul>
          {customer.previous_claims.map((previous) => (
            <li key={previous.claim_id}>
              <span className="mono">{previous.filed_on}</span>:{" "}
              {previous.summary}, {previous.outcome},{" "}
              {money(previous.amount_paid)}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
