import { expect, test, type APIRequestContext } from "@playwright/test";

// The agent is not run here, since tests never call a model. These tests play
// its part through the same API the agent uses.

interface RunResponse {
  run_id: number;
}

async function newRun(
  request: APIRequestContext,
  limit: number,
): Promise<string> {
  const response = await request.post("/api/runs", { data: { limit } });
  const body = (await response.json()) as RunResponse;
  return body.run_id.toString();
}

test("a to-do list written during a run shows on the queue page, in order, and the summary shows once it finishes", async ({
  page,
  request,
}) => {
  const runId = await newRun(request, 2);

  await request.put(`/api/runs/${runId}/todos`, {
    data: {
      todos: [
        { content: "CLM-1004", status: "todo" },
        { content: "CLM-1005", status: "todo" },
      ],
    },
  });

  await page.goto("/");
  await expect(page.locator(".todos li > span:first-child")).toHaveText([
    "CLM-1004",
    "CLM-1005",
  ]);

  await request.put(`/api/runs/${runId}/todos`, {
    data: {
      todos: [
        { content: "CLM-1004", status: "done" },
        { content: "CLM-1005", status: "in_progress" },
      ],
    },
  });
  await page.reload();
  await expect(
    page.locator(".todos li", { hasText: "CLM-1004" }).locator(".chip"),
  ).toHaveText("Done");

  for (const claimId of ["CLM-1004", "CLM-1005"]) {
    const start = await request.post(
      `/api/runs/${runId}/claims/${claimId}/start`,
    );
    expect(start.ok()).toBe(true);
    const decision = await request.post(`/api/claims/${claimId}/decision`, {
      data: {
        decision: "decline",
        payout: 0,
        reason: "Not covered.",
        policy_section: "Section 9",
      },
    });
    expect(decision.ok()).toBe(true);
  }

  const finish = await request.post(`/api/runs/${runId}/finish`, {
    data: { summary: "Two claims declined." },
  });
  expect(finish.ok()).toBe(true);

  await page.reload();
  await expect(page.getByText("Two claims declined.")).toBeVisible();
});

test("a claim that fails twice is left for a handler, shown on the queue and the claim page", async ({
  page,
  request,
}) => {
  const runId = await newRun(request, 1);
  const claimId = "CLM-1006";

  for (let attempt = 0; attempt < 2; attempt++) {
    const start = await request.post(
      `/api/runs/${runId}/claims/${claimId}/start`,
    );
    expect(start.ok()).toBe(true);
    const release = await request.post(`/api/claims/${claimId}/release`, {
      data: { reason: "model unavailable" },
    });
    expect(release.ok()).toBe(true);
  }

  await page.goto("/");
  await expect(
    page.locator("tr", { hasText: claimId }).locator(".chip"),
  ).toHaveText("Left for a handler");

  await page.goto(`/#/claims/${claimId}`);
  await expect(page.locator(".chip").first()).toHaveText("Left for a handler");
});

test("a posted read shows on the claim page under what the agent read", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1007";
  const read = await request.post(`/api/claims/${claimId}/reads`, {
    data: { document: "wording", section: 3 },
  });
  expect(read.ok()).toBe(true);

  await page.goto(`/#/claims/${claimId}`);
  await expect(page.getByText("Policy wording, 3. Trip Delay")).toBeVisible();
});
