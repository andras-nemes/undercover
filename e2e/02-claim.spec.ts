import { expect, test, type APIRequestContext } from "@playwright/test";

// The agent is not run here, since tests never call a model. These tests play
// its part through the same API the agent uses.
async function decide(
  request: APIRequestContext,
  claimId: string,
  payout: number,
) {
  const response = await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout,
      reason: "Covered by the policy wording.",
      policy_section: "Section 3, Trip Delay",
    },
  });
  expect(response.ok()).toBe(true);
}

test("a paid claim shows its decision, reason and payout", async ({
  page,
  request,
}) => {
  await decide(request, "CLM-1001", 420);
  const payment = await request.post("/api/claims/CLM-1001/payment", {
    data: { amount: 420 },
  });
  expect(payment.ok()).toBe(true);

  await page.goto("/#/claims/CLM-1001");
  await expect(page.locator(".chip")).toHaveText("Decided");
  await expect(page.locator(".outcome")).toHaveText("Approved $420.00");
  await expect(page.getByText("Covered by the policy wording.")).toBeVisible();
  await expect(page.getByText("Policy: Section 3, Trip Delay")).toBeVisible();
});

test("a payout over the limit waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  await decide(request, "CLM-1002", 1250);
  const payment = await request.post("/api/claims/CLM-1002/payment", {
    data: { amount: 1250 },
  });
  expect(payment.status()).toBe(409);

  await page.goto("/#/claims/CLM-1002");
  await expect(page.locator(".chip")).toHaveText("Waiting for sign-off");

  await page.getByRole("combobox").selectOption({ label: "Dana Whitfield" });
  await page.getByRole("button", { name: "Sign off and pay" }).click();

  await expect(page.locator(".chip")).toHaveText("Decided");
  await expect(
    page.getByText(/after sign-off by Dana Whitfield/),
  ).toBeVisible();
  await expect(page.getByText(/Paid \$1,250\.00/)).toBeVisible();
});

test("the agent's steps appear in order", async ({ page, request }) => {
  for (const text of ["Started on CLM-1003", "get_claim", "Done"]) {
    const event = await request.post("/api/claims/CLM-1003/events", {
      data: { kind: "note", text },
    });
    expect(event.ok()).toBe(true);
  }
  await page.goto("/#/claims/CLM-1003");
  await expect(page.locator(".steps li .step-text")).toHaveText([
    "Started on CLM-1003",
    "get_claim",
    "Done",
  ]);
});
