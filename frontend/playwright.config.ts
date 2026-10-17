import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests run against a running stack with demo data:
 *   backend: `uv run python manage.py seed_demo && uv run python manage.py runserver`
 *   frontend: `npm run dev`
 * Point E2E_BASE_URL at the production-like Docker stack to test that instead.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  // The tests share one demo database and move the same jobs, so run them one at a time.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
  ],
});
