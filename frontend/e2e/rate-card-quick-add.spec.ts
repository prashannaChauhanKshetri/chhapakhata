import { expect, test } from '@playwright/test';

import { signIn } from './helpers';

test('owner adds a new material to the rate card while taking an order', async ({ browser }) => {
  const name = `Canvas ${Date.now() % 100000}`;
  const page = await signIn(browser, 'owner');
  await page.goto('/orders/new');

  const media = page.getByRole('combobox', { name: 'Media' }).first();
  await media.click();
  await media.fill(name);
  await page.getByRole('option', { name: `Add “${name}” to the rate card` }).click();

  // The rate-card form opens with the typed name; the order stays where it was.
  const dialog = page.getByRole('dialog', { name: 'Add to the rate card' });
  await expect(dialog.getByRole('textbox', { name: 'Name' })).toHaveValue(name);
  await dialog.getByRole('textbox', { name: 'Rate per sq ft' }).fill('45');
  await dialog
    .getByRole('button', { name: /Save|Add/ })
    .last()
    .click();
  await expect(dialog).toBeHidden();
  await expect(page).toHaveURL(/\/orders\/new$/);

  // The new item is chosen on the order line and priced from the rate card.
  await expect(media).toHaveValue(new RegExp(`^${name} · Rs 45/sq ft`));
  await page.getByRole('textbox', { name: 'Width' }).first().fill('4');
  await page.getByRole('textbox', { name: 'Height' }).first().fill('3');
  await expect(page.getByText('12 sq ft · 12 × Rs 45')).toBeVisible();

  // "Open rate card…" goes to the items page (after confirming the unsaved order).
  await media.click();
  await media.fill('');
  await page.getByRole('option', { name: 'Open rate card…' }).click();
  await page.getByRole('button', { name: 'Leave and discard' }).click();
  await expect(page).toHaveURL(/\/settings\/rate-card$/);
  // In the rate-card table (the "added" notice may still show the name too).
  await expect(page.getByRole('cell', { name, exact: true })).toBeVisible();
});

test('front desk cannot change the rate card from an order', async ({ browser }) => {
  const page = await signIn(browser, 'frontdesk');
  await page.goto('/orders/new');
  const media = page.getByRole('combobox', { name: 'Media' }).first();
  await media.click();
  await media.fill('Something new');
  await expect(page.getByText('Not on the rate card. Ask the owner to add it.')).toBeVisible();
  await expect(page.getByRole('option', { name: /to the rate card|Open rate card/ })).toHaveCount(
    0,
  );
});
