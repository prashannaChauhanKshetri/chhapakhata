import { expect, type Browser, type Page } from '@playwright/test';

export const PASSWORD = process.env.E2E_PASSWORD ?? 'Demo@2083';

export async function signIn(browser: Browser, username: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto('/');
  await page.getByLabel('Username').fill(username);
  await page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
  return page;
}

/** Choose an option in a Mantine Select by typing part of its label. */
export async function choose(
  page: Page,
  label: string | RegExp,
  search: string,
  option: string | RegExp,
) {
  const input = page.getByRole('combobox', { name: label }).first();
  await input.click();
  await input.fill(search);
  await page.getByRole('option', { name: option }).first().click();
}
