import { expect, test } from '@playwright/test';

import { signIn } from './helpers';

/** A small work log in the shop's own column layout (CSV works like .xlsx). */
function workLog(customer: string): string {
  const header =
    'Date,Particular,Address,Items,Height,Width,Qty,SQFT,Rate,Amount,Details,Payment S,Payment M,Discount,Balance';
  const rows = [
    `2083.04.10,${customer},Nepalgunj,Banner,3,5,1,15,30,450,Opening banner,200,eSewa,0,250`,
    `2083.04.10,${customer},Nepalgunj,Normal Photo,,,4,0,160,640,Passport size,0,,40,600`,
    `2083.04.12,${customer},Nepalgunj,Banner,2,4,1,8,30,240,Notice,0,,0,240`,
  ];
  return [header, ...rows].join('\n');
}

test('owner imports the Excel work log once, and dues reach the ledger', async ({ browser }) => {
  const customer = `Import Test ${Date.now()}`;
  const file = {
    name: 'Work_Details.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(workLog(customer)),
  };
  const page = await signIn(browser, 'owner');
  await page.goto('/settings/import-export');

  // Preview first: nothing is saved yet.
  await page.locator('input[type=file]').setInputFiles(file);
  await expect(page.getByText('Ready to import 3 rows as 2 orders')).toBeVisible();
  await expect(page.getByText('Payment mode ← Payment M')).toBeVisible();
  await expect(page.getByText(new RegExp(`1 new \\(${customer}\\)`))).toBeVisible();

  await page.getByRole('button', { name: 'Import 3 rows' }).click();
  await expect(page.getByText('Imported 3 rows into 2 orders')).toBeVisible();

  // Balance = 450 + 640 + 240 − 40 discount − 200 paid = 1,090.
  await page.getByRole('link', { name: 'Open customer balances' }).click();
  await page.getByRole('combobox', { name: 'Period' }).click();
  await page.getByRole('option', { name: 'All time' }).click();
  await page.getByPlaceholder('Name or phone').fill(customer);
  const row = page.getByRole('row').filter({ hasText: customer });
  await expect(row).toContainText('1,090.00 Dr');

  // Uploading the same sheet again adds nothing.
  await page.goto('/settings/import-export');
  await page.locator('input[type=file]').setInputFiles(file);
  await expect(page.getByText('Nothing new to import')).toBeVisible();
  await expect(page.getByText('3 rows were imported before and are skipped.')).toBeVisible();

  // Front desk cannot import.
  const desk = await signIn(browser, 'frontdesk');
  await desk.goto('/settings/import-export');
  await expect(desk.getByText('Import the Excel work log')).toHaveCount(0);
});
