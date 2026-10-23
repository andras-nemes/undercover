import { expect, it } from "vitest";
import { parseHash } from "./router";

it("picks the view for an address", () => {
  expect(parseHash("")).toEqual({ name: "queue" });
  expect(parseHash("#/")).toEqual({ name: "queue" });
  expect(parseHash("#/instructions")).toEqual({ name: "instructions" });
  expect(parseHash("#/claims/CLM-1001")).toEqual({
    name: "claim",
    id: "CLM-1001",
  });
  expect(parseHash("#/claims/")).toEqual({ name: "missing" });
  expect(parseHash("#/other")).toEqual({ name: "missing" });
});
