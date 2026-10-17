import { expect, test } from '@playwright/test';

import { signIn } from './helpers';

test('a name with no match can be added as a customer straight from the search box', async ({
  browser,
}) => {
  const name = `Walk-in ${Date.now()}`;
  const page = await signIn(browser, 'frontdesk');
  await page.goto('/orders/new');

  const search = page.getByRole('combobox', { name: 'Customer' });
  await search.click();
  await search.fill(name);
  await page.getByRole('option', { name: `Add “${name}” as a new customer` }).click();

  // The form opens with the name filled in; PAN and phone are optional.
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('textbox', { name: 'Name' })).toHaveValue(name);
  await dialog.getByRole('button', { name: 'Add customer' }).click();

  // Back on the order with the new customer chosen.
  await expect(dialog).toBeHidden();
  await expect(search).toHaveValue(name);

  // The customer list offers the same shortcut when a search finds nobody.
  await page.goto(`/customers?q=${encodeURIComponent(`${name} Jr`)}`);
  await expect(page.getByRole('button', { name: `Add “${name} Jr”` })).toBeVisible();
});
