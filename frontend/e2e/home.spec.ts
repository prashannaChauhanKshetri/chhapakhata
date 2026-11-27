import { expect, test } from '@playwright/test';

import { PASSWORD } from './helpers';

test('a visitor sees what ChhapaKhata does, how to get it, and can sign in', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Every job and every rupee, from counter to collection.',
  );
  await expect(page.getByText('Busy shops lose money in small ways, every day.')).toBeVisible();
  const email = page.getByRole('link', { name: 'prashannachauhankshetri@gmail.com' });
  await expect(email).toHaveAttribute('href', /^mailto:prashannachauhankshetri@gmail\.com/);
  // Nothing scrolls sideways.
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBe(
    0,
  );

  await page.getByRole('button', { name: 'Sign in' }).first().click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Username').fill('owner');
  await page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
  await expect(page).toHaveURL(/\/$/); // the dashboard

  // Signing out shows the sign-in page, not the home page.
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('menuitem', { name: /Sign out/ }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
