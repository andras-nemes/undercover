import { expect, test } from "@playwright/test";

test("the queue shows 25 claims, all waiting", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("row")).toHaveCount(26);
  await expect(
    page.getByRole("cell", { name: "Waiting", exact: true }),
  ).toHaveCount(25);
  await expect(page.getByRole("link", { name: "CLM-1001" })).toBeVisible();
});

test("the instructions page shows the agent instructions", async ({
  page,
  request,
}) => {
  const text = await (await request.get("/api/instructions/claim")).text();
  const [firstLine = ""] = text.split("\n");
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "Agent instructions" }),
  ).toBeVisible();
  await expect(page.getByRole("main")).toContainText(firstLine);
});
