import { expect, it } from "vitest";
import { label, money } from "./format";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0.5)).toBe("$0.50");
});

it("makes a readable label", () => {
  expect(label("trip_delay")).toBe("Trip delay");
});
