import { expect, test } from '@playwright/test';

import { signIn } from './helpers';

test('unsaved orders are protected and shortcuts work', async ({ browser }) => {
  const page = await signIn(browser, 'frontdesk');

  // Shortcuts: N starts an order, / jumps to search.
  await page.keyboard.press('n');
  await expect(page).toHaveURL(/\/orders\/new$/);

  // Prevent errors: leaving a half-entered order asks first.
  await page.getByRole('textbox', { name: 'Width' }).first().fill('4');
  await page.getByRole('link', { name: 'Customers' }).click();
  const dialog = page.getByRole('dialog', { name: 'Leave without saving?' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Keep editing' }).click();
  await expect(page).toHaveURL(/\/orders\/new$/);
  await expect(page.getByRole('textbox', { name: 'Width' }).first()).toHaveValue('4');
  await page.getByRole('link', { name: 'Customers' }).click();
  await page.getByRole('button', { name: 'Leave and discard' }).click();
  await expect(page).toHaveURL(/\/customers$/);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: 'Search customers' })).toBeVisible();

  await page.keyboard.press('/');
  await expect(page.getByRole('textbox', { name: 'Search customers' })).toBeFocused();
  await page.keyboard.press('Escape');
  await page.locator('body').click();
  await page.keyboard.press('Shift+?');
  await expect(page.getByRole('dialog', { name: 'Keyboard shortcuts' })).toBeVisible();
});

test('a job moved by mistake can be put back with Undo', async ({ browser }) => {
  const page = await signIn(browser, 'operator');
  await page.goto('/production');
  const finishing = page.getByRole('region', { name: 'Finishing / Framing' });
  const card = finishing.locator('[data-job]').first();
  await expect(card).toBeVisible();
  const jobNo = await card.getAttribute('data-job');

  await card.getByRole('button', { name: 'Ready' }).click();
  const ready = page.getByRole('region', { name: 'Ready for collection' });
  await expect(ready.locator(`[data-job="${jobNo}"]`)).toBeVisible();

  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(finishing.locator(`[data-job="${jobNo}"]`)).toBeVisible();
});
