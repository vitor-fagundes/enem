import { expect, test } from "@playwright/test";
test("foundation page is available in Portuguese", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("enem-rei");
  await expect(
    page.getByRole("heading", { level: 1, name: "enem-rei", exact: true }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
});
