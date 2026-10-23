import type { ClaimDetail } from "./api";
import { DOCUMENT_LABELS } from "./format";

export function ReadsPanel({ claim }: Readonly<{ claim: ClaimDetail }>) {
  return (
    <section className="panel">
      <h2>What the agent read</h2>
      {claim.reads.length === 0 ? (
        <p className="note">The agent has not read any sections yet.</p>
      ) : (
        <ul>
          {claim.reads.map((read) => (
            <li key={`${read.document}-${read.section.toString()}`}>
              {DOCUMENT_LABELS[read.document]}, {read.section}. {read.title}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
