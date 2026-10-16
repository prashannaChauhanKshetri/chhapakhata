import { expect, test, type Locator, type Page } from '@playwright/test';

import { signIn } from './helpers';

/** Drag with real pointer steps: the board starts a drag after a 6 px move. */
async function drag(page: Page, from: Locator, to: Locator) {
  const a = await from.boundingBox();
  const b = await to.boundingBox();
  if (!a || !b) throw new Error('Card or column is not visible');
  await page.mouse.move(a.x + a.width / 2, a.y + 20);
  await page.mouse.down();
  await page.mouse.move(a.x + a.width / 2 + 10, a.y + 30, { steps: 4 });
  await page.mouse.move(b.x + b.width / 2, b.y + 80, { steps: 12 });
  await page.mouse.up();
}

test('front desk drags a job from Design to Ready for print, but not to Printing', async ({
  browser,
}) => {
  const page = await signIn(browser, 'frontdesk');
  await page.goto('/production');
  const design = page.getByRole('region', { name: 'Design pending / Proof sent' });
  const ready = page.getByRole('region', { name: 'Ready for print' });
  const printing = page.getByRole('region', { name: 'Printing' });
  const card = design.locator('[data-job]').first();
  await expect(card).toBeVisible();
  const jobNo = await card.getAttribute('data-job');

  // Printing belongs to operators: the drop is refused and the card stays put.
  await drag(page, card, printing);
  await expect(page.getByText(`${jobNo} cannot move to Printing`)).toBeVisible();
  await expect(design.locator(`[data-job="${jobNo}"]`)).toBeVisible();

  await drag(page, design.locator(`[data-job="${jobNo}"]`), ready);
  await expect(ready.locator(`[data-job="${jobNo}"]`)).toBeVisible();
  await expect(page.getByText(`${jobNo} moved to`)).toBeVisible();
});
