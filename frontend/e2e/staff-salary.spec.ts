import { expect, test } from '@playwright/test';

import { signIn } from './helpers';

test('owner adds a worker, marks a day, gives an advance, pays and undoes the salary', async ({
  browser,
}) => {
  const name = `Hari ${Date.now() % 100000}`;
  const owner = await signIn(browser, 'owner');

  // Add the worker (joins today).
  await owner.goto('/staff/list');
  await owner.getByRole('button', { name: 'Add staff' }).click();
  const form = owner.getByRole('dialog');
  await form.getByRole('textbox', { name: 'Name' }).fill(name);
  await form.getByRole('textbox', { name: 'Monthly salary (Rs)' }).fill('15000');
  await form.getByRole('button', { name: 'Add staff' }).click();
  await expect(form).toBeHidden();
  await expect(owner.getByText(name)).toBeVisible();

  // Today: absent on a working day, or worked on Saturday.
  await owner.getByRole('tab', { name: 'Attendance' }).click();
  const control = owner.getByRole('radiogroup', { name: `Attendance of ${name}` });
  const saturday = (await control.getByText('Worked').count()) > 0;
  await control.getByText(saturday ? 'Worked' : 'Absent').click();
  await expect(control.getByRole('radio', { name: saturday ? 'Worked' : 'Absent' })).toBeChecked();

  // Salary: the mark shows; give an advance and pay.
  await owner.getByRole('tab', { name: 'Salary' }).click();
  const row = owner.getByRole('row').filter({ hasText: name });
  await expect(row.getByText('Not paid')).toBeVisible();
  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await owner.getByRole('menuitem', { name: 'Give advance' }).click();
  await owner.getByRole('dialog').getByRole('textbox', { name: 'Amount (Rs)' }).fill('500');
  await owner.getByRole('dialog').getByRole('button', { name: 'Give advance' }).click();
  await expect(owner.getByText(/Advance Rs\. 500\.00 to/)).toBeVisible();

  await row.click(); // the breakdown
  await expect(owner.getByText('Advance on', { exact: false })).toBeVisible();
  await expect(owner.getByText(saturday ? /Saturdays worked: 1/ : /Days absent: 1/)).toBeVisible();

  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await owner.getByRole('menuitem', { name: 'Pay salary' }).click();
  const slip = owner.context().waitForEvent('page');
  await owner
    .getByRole('dialog')
    .getByRole('button', { name: /^Pay Rs\./ })
    .click();
  await expect(owner.getByText(new RegExp(`paid to ${name}`))).toBeVisible();
  await (await slip).close();
  await expect(row.getByText('Paid', { exact: true })).toBeVisible();

  // The paid month is locked; undoing opens it again.
  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await owner.getByRole('menuitem', { name: 'Undo payment' }).click();
  await owner.getByRole('dialog').getByRole('textbox').fill('Testing');
  await owner.getByRole('dialog').getByRole('button', { name: 'Undo payment' }).click();
  await expect(row.getByText('Not paid')).toBeVisible();
});

test('front desk cannot open staff and salary', async ({ browser }) => {
  const desk = await signIn(browser, 'frontdesk');
  await expect(desk.getByRole('link', { name: 'Staff & salary' })).toHaveCount(0);
  await desk.goto('/staff/salary');
  await expect(desk.getByText('You do not have access to this page')).toBeVisible();
});
