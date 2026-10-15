import { expect, test } from '@playwright/test';

import { choose, signIn } from './helpers';

test('counter to delivery: order, print with material, deliver, invoice and settle', async ({
  browser,
}) => {
  // 1. Front desk takes the order.
  const desk = await signIn(browser, 'frontdesk');
  await desk.goto('/orders/new');
  await choose(desk, 'Customer', 'Gita', /Gita Tharu/);
  await choose(desk, 'Media', 'Star', /Star Flex/);
  await desk.getByRole('textbox', { name: 'Width' }).fill('6');
  await desk.getByRole('textbox', { name: 'Height' }).fill('3');
  // 6 × 3 ft = 18 sq ft × Rs 35 = 630, + 13% VAT = 711.90 (priced by the server)
  await expect(desk.getByText('Rs. 711.90').first()).toBeVisible();
  await desk.getByRole('button', { name: 'Confirm order' }).first().click();
  await expect(desk.getByText('Confirmed', { exact: true })).toBeVisible();
  const orderNo = (await desk.getByRole('heading', { level: 1 }).textContent())!.trim();
  expect(orderNo).toMatch(/^ORD-/);
  const jobNo = (await desk
    .getByText(/^JOB-\d+$/)
    .first()
    .textContent())!.trim();

  // Front desk approves the proof: Design → Ready for print.
  await desk.goto('/production');
  await desk.getByPlaceholder('Job, order, customer or material').fill(jobNo);
  await desk
    .locator(`[data-job="${jobNo}"]`)
    .getByRole('button', { name: 'Ready for print' })
    .click();
  await expect(desk.getByText(/moved to Ready for print/)).toBeVisible();

  // 2. Operator prints it and records the roll used when leaving Printing.
  const operator = await signIn(browser, 'operator');
  await operator.goto('/production');
  const card = operator.locator(`[data-job="${jobNo}"]`);
  await card.getByRole('button', { name: 'Printing' }).click();
  await expect(operator.getByText(/moved to Printing/)).toBeVisible();
  await card.getByRole('button', { name: 'Finishing' }).click();
  const dialog = operator.getByRole('dialog');
  await expect(dialog.getByRole('textbox', { name: 'Sq ft used' })).toHaveValue('18');
  await dialog.getByRole('button', { name: 'Save and move' }).click();
  await expect(operator.getByText(/moved to Finishing/)).toBeVisible();
  await card.getByRole('button', { name: 'Ready', exact: true }).click();
  await expect(operator.getByText(/moved to Ready/)).toBeVisible();

  // Operators cannot reach billing.
  await operator.goto('/invoices');
  await expect(operator.getByText('You do not have access to this page')).toBeVisible();

  // 3. Front desk delivers: invoice issued, full cash payment, order closed.
  await desk.goto('/orders');
  await desk.getByPlaceholder('Search order no., customer, phone or description').fill(orderNo);
  await desk.getByRole('link', { name: orderNo }).click();
  await desk.getByRole('button', { name: 'Deliver' }).click();
  await desk.getByRole('dialog').getByRole('button', { name: 'Mark delivered' }).click();
  await expect(desk.getByText('Fully paid. Thank you!')).toBeVisible();
  await desk.getByRole('button', { name: 'Done' }).click();
  await expect(desk.getByText('Delivered', { exact: true }).first()).toBeVisible();
  await expect(desk.getByRole('link', { name: /^INV-/ })).toBeVisible();
});
