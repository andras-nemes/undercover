import { useState } from "react";
import { post, type Run } from "./api";
import { RUN_STATUS_LABELS, TODO_STATUS_LABELS } from "./format";
import { useApi } from "./useApi";

const DEFAULT_TRIAL = "5";

function isRunning(run: Run | null): boolean {
  return run?.status === "running";
}

export function RunPanel({ onStarted }: Readonly<{ onStarted: () => void }>) {
  const {
    data: run,
    error,
    reload,
  } = useApi<Run | null>("/api/runs/latest", isRunning);
  const [trial, setTrial] = useState(DEFAULT_TRIAL);
  const [runError, setRunError] = useState<string | null>(null);
  const busy = isRunning(run);

  const start = (limit: number) => {
    post("/api/runs", { limit })
      .then(() => {
        setRunError(null);
        reload();
        onStarted();
      })
      .catch((failure: unknown) => {
        setRunError(String(failure));
      });
  };

  return (
    <section className="panel run-panel">
      <h2>Queue run</h2>
      {error && <p role="alert">The latest run could not be loaded.</p>}
      {!error && run === null && (
        <p className="note">No run has started yet.</p>
      )}
      {run && (
        <>
          <p className="note">
            {RUN_STATUS_LABELS[run.status]}
            {run.limit > 0 && `, capped at ${run.limit.toString()}`}
          </p>
          {run.status === "finished" && <p>{run.summary}</p>}
          {run.status === "failed" && <p role="alert">{run.summary}</p>}
          {run.todos.length > 0 && (
            <ol className="todos">
              {run.todos.map((todo) => (
                <li key={todo.content}>
                  <span>{todo.content}</span>
                  <span className={`chip chip-${todo.status}`}>
                    {TODO_STATUS_LABELS[todo.status]}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
      <div className="actions">
        <button
          className="primary"
          disabled={busy}
          onClick={() => {
            start(0);
          }}
        >
          Run all waiting
        </button>
        <label className="trial">
          Trial of
          <input
            type="number"
            min={1}
            value={trial}
            onChange={(event) => {
              setTrial(event.target.value);
            }}
          />
        </label>
        <button
          disabled={busy}
          onClick={() => {
            start(Number(trial) || Number(DEFAULT_TRIAL));
          }}
        >
          Run a trial
        </button>
      </div>
      {runError && <p role="alert">{runError}</p>}
    </section>
  );
}
