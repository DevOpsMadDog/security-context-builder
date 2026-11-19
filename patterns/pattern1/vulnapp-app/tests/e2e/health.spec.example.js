// Optional Playwright example, not part of the dependency-free default CI.
// To enable in the real app repo:
//   npm install --save-dev @playwright/test
//   npx playwright install --with-deps chromium
//   add "test:e2e": "playwright test" to scripts, commit package-lock.json
//   start the sandbox/local app at PLAYWRIGHT_BASE_URL before running tests.
import { test, expect } from "@playwright/test";

test("health endpoint responds", async ({ request }) => {
  const base = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
  const response = await request.get(base + "/health");
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toEqual({ status: "ok" });
});
