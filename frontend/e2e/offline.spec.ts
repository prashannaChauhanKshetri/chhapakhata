/// <reference lib="dom" />
import { expect, test } from '@playwright/test';

import { PASSWORD } from './helpers';

/**
 * Needs the production build with its service worker, served where the test
 * browser trusts it (localhost counts as secure):
 *   cd frontend && npm run build && npx vite preview --port 4174
 *   E2E_BASE_URL=http://127.0.0.1:4174 npx playwright test offline
 */
test.skip(!process.env.E2E_BASE_URL?.includes(':417'), 'Runs against the production build');
test.use({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 }, isMobile: true });

test('installable app keeps working when the shop computer is off', async ({ page, context }) => {
  await page.goto('/');
  await page.getByLabel('Username').fill('frontdesk');
  await page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();

  // The service worker stores the app on the device.
  await expect
    .poll(() => page.evaluate(async () => !!(await navigator.serviceWorker.ready).active), {
      timeout: 20_000,
    })
    .toBe(true);
  const manifest = await page.request.get('/manifest.webmanifest');
  expect((await manifest.json()).display).toBe('standalone');

  // Load some data while online, then let the saved copy be written.
  await page.goto('/customers');
  await expect(page.getByText('Hotel Kalpana')).toBeVisible();
  await page.waitForTimeout(2_500);

  // The phone has Wi-Fi but the shop computer stops answering.
  await context.route('**/api/**', (route) => route.abort('connectionrefused'));
  await page.reload();
  await expect(page.getByText('The shop computer is not answering.')).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText('Hotel Kalpana')).toBeVisible();

  // Saving is refused with a clear message instead of failing halfway.
  await page.getByRole('button', { name: 'New customer' }).click();
  await page.getByRole('textbox', { name: 'Name' }).fill('Offline Test Customer');
  await page.getByRole('button', { name: 'Add customer' }).click();
  await expect(page.getByText(/Offline: the shop computer cannot be reached/)).toBeVisible();
  await page.screenshot({ path: 'test-results/offline-banner.png' });
  await page.keyboard.press('Escape');

  // Fully offline device: the app still opens from the device.
  await context.setOffline(true);
  await page.goto('/customers');
  await expect(page.getByText('This device is offline.')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('Hotel Kalpana')).toBeVisible();

  // Back online: the banner goes away by itself.
  await context.setOffline(false);
  await context.unroute('**/api/**');
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect(page.getByText('This device is offline.')).toBeHidden({ timeout: 20_000 });
});
