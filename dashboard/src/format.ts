import type {
  DocumentName,
  Outcome,
  RunStatus,
  Status,
  TodoStatus,
} from "./api";

export const STATUS_LABELS: Record<Status, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  awaiting_sign_off: "Waiting for sign-off",
  decided: "Decided",
  needs_handler: "Left for a handler",
};

export const OUTCOME_LABELS: Record<Outcome, string> = {
  approve: "Approved",
  decline: "Declined",
  refer: "Referred",
};

export const TODO_STATUS_LABELS: Record<TodoStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
  left_for_handler: "Left for a handler",
};

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  running: "Running",
  finished: "Finished",
  failed: "Failed",
};

export const DOCUMENT_LABELS: Record<DocumentName, string> = {
  wording: "Policy wording",
  manual: "Claims manual",
};

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function money(amount: number): string {
  return dollars.format(amount);
}

export function label(text: string): string {
  const spaced = text.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
