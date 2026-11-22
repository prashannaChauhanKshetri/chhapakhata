import { expect, test } from '@playwright/test';

import { choose, signIn } from './helpers';

test('a media not on the list is typed by hand with its own rate', async ({ browser }) => {
  const name = `Canvas ${Date.now() % 100000}`;
  const desk = await signIn(browser, 'frontdesk');
  await desk.goto('/orders/new');
  await choose(desk, 'Customer', 'Gita', /Gita Tharu/);

  const media = desk.getByRole('combobox', { name: 'Media' }).first();
  await media.click();
  await media.fill(name);
  await expect(desk.getByText('New: added to the media list when saved')).toBeVisible();

  // Sized, so it is priced per sq ft at the rate typed: 4 × 3 ft = 12 sq ft × Rs 50.
  await desk.getByRole('textbox', { name: 'Width' }).first().fill('4');
  await desk.getByRole('textbox', { name: 'Height' }).first().fill('3');
  await desk.getByRole('textbox', { name: 'Rate per sq ft' }).first().fill('50');
  await expect(desk.getByText('12 sq ft · 12 × Rs 50')).toBeVisible();

  await desk.getByRole('button', { name: 'Confirm order' }).first().click();
  await expect(desk.getByText('Confirmed', { exact: true })).toBeVisible();
  await expect(desk.locator('main table').getByText(name)).toBeVisible();

  // The next order offers the new name in the list.
  await desk.goto('/orders/new');
  const next = desk.getByRole('combobox', { name: 'Media' }).first();
  await next.click();
  await next.fill(name);
  await expect(desk.getByRole('option', { name })).toBeVisible();
});
