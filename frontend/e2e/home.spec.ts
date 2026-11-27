import { expect, test } from '@playwright/test';

import { PASSWORD } from './helpers';

test('a visitor sees what ChhapaKhata does, how to get it, and can sign in', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Every job and every rupee, from counter to collection.',
  );
  await expect(page.getByText('Busy shops lose money in small ways, every day.')).toBeVisible();
  // The address is shown in full, to read or copy.
  await expect(page.getByText('prashannachauhankshetri@gmail.com', { exact: true })).toBeVisible();
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

test('the email button offers Gmail, an email app or a copy; legal pages and the cookie note', async ({
  page,
  request,
}) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Get it for your shop' }).click();
  await expect(page.getByRole('menuitem', { name: 'Write in Gmail' })).toHaveAttribute(
    'href',
    /^https:\/\/mail\.google\.com\/mail\/\?view=cm&fs=1&to=prashannachauhankshetri@gmail\.com/,
  );
  await expect(page.getByRole('menuitem', { name: 'Use my email app' })).toHaveAttribute(
    'href',
    /^mailto:prashannachauhankshetri@gmail\.com/,
  );
  await page.keyboard.press('Escape');

  // The cookie note: once, until OK.
  const note = page.getByRole('region', { name: 'Cookies' });
  await expect(note).toBeVisible();
  await note.getByRole('button', { name: 'OK' }).click();
  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(note).toHaveCount(0);

  await page.getByRole('button', { name: 'Terms' }).click();
  await expect(page.getByRole('heading', { name: 'Terms of service' })).toBeVisible();
  await page.getByRole('button', { name: 'privacy policy' }).first().click();
  await expect(page.getByRole('heading', { name: 'Privacy policy' })).toBeVisible();
  await expect(page).toHaveURL(/\/privacy$/);

  // For search engines: only the public pages.
  const robots = await (await request.get('/robots.txt')).text();
  expect(robots).toContain('Disallow: /');
  expect(robots).toContain('Sitemap: https://chhapakhata.tech/sitemap.xml');
  expect(await (await request.get('/sitemap.xml')).text()).toContain(
    'https://chhapakhata.tech/privacy',
  );
});
