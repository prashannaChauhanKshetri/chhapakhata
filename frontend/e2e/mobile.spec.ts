import { expect, test } from '@playwright/test';

import { PASSWORD } from './helpers';

const SCREENS = [
  '/',
  '/orders',
  '/orders/new',
  '/customers',
  '/production',
  '/inventory',
  '/purchases',
  '/invoices',
  '/payments',
  '/ledger',
  '/reports',
  '/insights',
  '/settings/shop',
];

test('on an iPhone every screen fits the width and lists show as cards', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Username').fill('owner');
  await page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();

  for (const path of SCREENS) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    const [scrollWidth, width] = await page.evaluate(() => [
      document.documentElement.scrollWidth,
      window.innerWidth,
    ]);
    expect(scrollWidth, `${path} scrolls sideways`).toBeLessThanOrEqual(width);
  }

  // Orders: one card per order with its total, and no table cut off at the edge.
  await page.goto('/orders');
  const card = page
    .getByRole('button')
    .filter({ hasText: /ORD-\d+/ })
    .first();
  await expect(card).toBeVisible();
  await expect(page.locator('main table')).toHaveCount(0);
  await card.click();
  await expect(page).toHaveURL(/\/orders\/\d+$/);

  // Receive payment: every payment mode is on screen inside the dialog.
  await page.goto('/payments');
  await page.getByRole('button', { name: 'Receive payment' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText('Cheque')).toBeVisible();
  const [modesRight, dialogRight] = await page.evaluate(() => [
    document.querySelector('[role=dialog] .mantine-SegmentedControl-root')!.getBoundingClientRect()
      .right,
    document.querySelector('.mantine-Modal-content')!.getBoundingClientRect().right,
  ]);
  expect(modesRight).toBeLessThanOrEqual(dialogRight);
});
