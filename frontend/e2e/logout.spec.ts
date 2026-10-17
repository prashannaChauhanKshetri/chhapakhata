import { expect, test } from '@playwright/test';

import { signIn } from './helpers';

test('signing out returns to the login screen and ends the session', async ({ browser }) => {
  const page = await signIn(browser, 'owner');
  await page.goto('/settings/shop');
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();

  // The server session is gone too: a reload must not sign back in.
  await page.reload();
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
  const me = await page.request.get('/api/v1/auth/me/');
  expect(me.status()).toBe(403);

  // Signing in again as someone else shows their screens, not the last user's.
  await page.getByLabel('Username').fill('operator');
  await page.getByRole('textbox', { name: 'Password' }).fill('Demo@2083');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: 'Account menu' })).toContainText('Ram Thapa');
  await expect(page.getByRole('link', { name: 'Settings' })).toHaveCount(0);
});
