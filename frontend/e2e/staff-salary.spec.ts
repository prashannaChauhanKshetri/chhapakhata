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
  await form.getByRole('textbox', { name: 'Saturday pay (Rs)' }).fill('800');
  await form.getByRole('button', { name: 'Add staff' }).click();
  await expect(form).toBeHidden();
  await expect(owner.getByText(name)).toBeVisible();
  await expect(
    owner.getByRole('row').filter({ hasText: name }).getByText('Rs. 800.00'),
  ).toBeVisible();

  // Today: absent on a working day, or worked on Saturday.
  await owner.getByRole('tab', { name: 'Attendance' }).click();
  const control = owner.getByRole('radiogroup', { name: `Attendance of ${name}` });
  const saturday = (await control.getByText('Worked').count()) > 0;
  await control.getByText(saturday ? 'Worked' : 'Absent').click();
  await expect(control.getByRole('radio', { name: saturday ? 'Worked' : 'Absent' })).toBeChecked();

  // Salary: the mark shows; give an advance and pay.
  await owner.getByRole('tab', { name: 'Salary' }).click();
  await expect(owner.getByText('Salary month (BS)')).toBeVisible();
  const row = owner.getByRole('row').filter({ hasText: name }).first();
  await expect(row.getByText('Not paid')).toBeVisible();
  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await owner.getByRole('menuitem', { name: 'Give advance' }).click();
  await owner.getByRole('dialog').getByRole('textbox', { name: 'Amount (Rs)' }).fill('500');
  await owner.getByRole('dialog').getByRole('button', { name: 'Give advance' }).click();
  await expect(owner.getByText(/Advance Rs\. 500\.00 to/)).toBeVisible();

  await row.click(); // the breakdown
  await expect(owner.getByText('Advance on', { exact: false })).toBeVisible();
  await expect(owner.getByText(saturday ? /Saturdays worked: 1/ : /Days absent: 1/)).toBeVisible();

  // The month is still running: Pay waits for its end …
  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await expect(
    owner.getByRole('menuitem', { name: 'Pay salary (after month end)' }),
  ).toBeDisabled();
  await owner.keyboard.press('Escape');

  // … unless the worker has left: today is their last day, so the month can be paid.
  await owner.getByRole('tab', { name: 'Staff' }).click();
  // Wait for the staff list: until then the row can still be the salary table's.
  await expect(owner.getByRole('button', { name: 'Add staff' })).toBeVisible();
  await owner.getByRole('row').filter({ hasText: name }).first().click();
  const edit = owner.getByRole('dialog');
  // The Miti text arrives a moment after the AD date (converted on the server).
  await expect(edit.getByLabel('Joined on (Miti)')).toHaveValue(/^\d{4}\.\d{2}\.\d{2}$/);
  const joined = await edit.getByLabel('Joined on (Miti)').inputValue();
  await edit.getByRole('switch', { name: 'Still working here' }).click();
  const lastDay = edit.getByLabel('Last working day (Miti)');
  await lastDay.fill(joined);
  await lastDay.press('Enter');
  // The Miti is converted on the server; save once the AD date shows it.
  await expect(edit.getByRole('button', { name: 'Last working day (AD)' })).toContainText(/\d{4}/);
  await edit.getByRole('button', { name: 'Save' }).click();
  await expect(edit).toBeHidden();
  await owner.getByRole('tab', { name: 'Salary' }).click();
  await expect(owner.getByText('Salary month (BS)')).toBeVisible();
  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await owner.getByRole('menuitem', { name: 'Pay salary', exact: true }).click();
  const slip = owner.context().waitForEvent('page');
  await owner
    .getByRole('dialog')
    .getByRole('button', { name: /^Pay Rs\./ })
    .click();
  await expect(owner.getByText(new RegExp(`paid to ${name}`))).toBeVisible();
  await (await slip).close();
  await expect(row.getByText('Paid', { exact: true })).toBeVisible();

  // The month calendar: the paid month cannot be changed.
  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await owner.getByRole('menuitem', { name: 'Attendance days' }).click();
  const calendar = owner.getByRole('dialog', { name: `${name} · Attendance` });
  await expect(calendar.getByText(/This month is paid/)).toBeVisible();
  await owner.keyboard.press('Escape');

  // The paid month is locked; undoing opens it again.
  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await owner.getByRole('menuitem', { name: 'Undo payment' }).click();
  await owner.getByRole('dialog').getByRole('textbox').fill('Testing');
  await owner.getByRole('dialog').getByRole('button', { name: 'Undo payment' }).click();
  await expect(row.getByText('Not paid')).toBeVisible();

  // Unlocked, today's mark is corrected from the calendar (joined today: the only open day).
  await row.getByRole('button', { name: `Actions for ${name}` }).click();
  await owner.getByRole('menuitem', { name: 'Attendance days' }).click();
  const today = calendar.locator('button:not([disabled])').filter({ hasText: /\d/ });
  await expect(today).toHaveCount(1);
  await today.click();
  await expect(calendar.getByText(saturday ? 'Saturdays worked: 0' : 'Absent: 0')).toBeVisible();
});

test('front desk cannot open staff and salary', async ({ browser }) => {
  const desk = await signIn(browser, 'frontdesk');
  await expect(desk.getByRole('link', { name: 'Staff & salary' })).toHaveCount(0);
  await desk.goto('/staff/salary');
  await expect(desk.getByText('You do not have access to this page')).toBeVisible();
});

test('a worker already here starts from a balance up to last month', async ({ browser }) => {
  const name = `Sita ${Date.now() % 100000}`;
  const owner = await signIn(browser, 'owner');
  await owner.goto('/staff/list');
  await owner.getByRole('button', { name: 'Add staff' }).click();
  const form = owner.getByRole('dialog');
  await form.getByText('Already working here').click();
  await expect(form.getByRole('textbox', { name: 'Joined on' })).toHaveCount(0);
  await form.getByRole('textbox', { name: 'Name' }).fill(name);
  await form.getByRole('textbox', { name: 'Monthly salary (Rs)' }).fill('12000');
  const month = await form.getByRole('combobox', { name: 'Up to the end of' }).inputValue();
  expect(month).toMatch(/^[A-Z][a-z]+ \d{4}$/); // last month, e.g. "Kartik 2083"
  await form.getByRole('textbox', { name: 'Amount (Rs)' }).fill('2000');
  await form.getByText('Worker owes the shop').click();
  await form.getByRole('button', { name: 'Add staff' }).click();
  await expect(form).toBeHidden();
  await expect(
    owner.getByRole('row').filter({ hasText: name }).getByText(`owes the shop, to ${month}`),
  ).toBeVisible();

  // This month: the old advance comes off; last month: nothing to pay.
  await owner.getByRole('tab', { name: 'Salary' }).click();
  await expect(owner.getByText('Salary month (BS)')).toBeVisible();
  const row = owner.getByRole('row').filter({ hasText: name }).first();
  await row.click();
  await expect(owner.getByText(`Balance up to ${month}`)).toBeVisible();
  await expect(owner.getByText('Owed by the worker from before (old advance)')).toBeVisible();
  await owner.getByRole('button', { name: 'Previous month' }).click();
  await expect(owner.getByText(month, { exact: true })).toBeVisible();
  await expect(owner.getByRole('row').filter({ hasText: name })).toHaveCount(0);
});

test('a day is picked from the Nepali calendar and shows in the month register', async ({
  browser,
}) => {
  const name = `Gita ${Date.now() % 100000}`;
  const owner = await signIn(browser, 'owner');
  await owner.goto('/staff/list');
  await owner.getByRole('button', { name: 'Add staff' }).click();
  const form = owner.getByRole('dialog');
  await form.getByText('Already working here').click();
  await form.getByRole('textbox', { name: 'Name' }).fill(name);
  await form.getByRole('textbox', { name: 'Monthly salary (Rs)' }).fill('10000');
  await form.getByRole('button', { name: 'Add staff' }).click();
  await expect(form).toBeHidden();

  // The Miti box opens a BS calendar; choose the 1st of this month.
  await owner.getByRole('tab', { name: 'Attendance' }).click();
  await owner.getByRole('textbox', { name: 'Day (Miti)' }).click();
  const first = owner.getByRole('button', { name: /^1 [A-Z][a-z]+ \d{4}$/ });
  const month = (await first.getAttribute('aria-label'))!.slice(2); // e.g. "Mangsir 2083"
  await first.click();
  await expect(owner.getByText(`1 ${month}`, { exact: true })).toBeVisible();

  // Mark the day; the register shows it, and a box there switches it back.
  const register = owner.locator('table');
  const box = register.getByRole('button', { name: new RegExp(`^${name}, 1 ${month}: `) });
  const saturday = (await box.getAttribute('aria-label'))!.endsWith('Off');
  const control = owner.getByRole('radiogroup', { name: `Attendance of ${name}` });
  await control.getByText(saturday ? 'Worked' : 'Absent').click();
  await expect(box).toHaveText(saturday ? 'W' : 'A');
  await box.click();
  await expect(box).toHaveText(saturday ? '' : 'P');
  await expect(control.getByRole('radio', { name: saturday ? 'Off' : 'Present' })).toBeChecked();
});

test('a worker added by mistake is deleted; one with an advance can only leave', async ({
  browser,
}) => {
  const owner = await signIn(browser, 'owner');
  const add = async (name: string) => {
    await owner.goto('/staff/list');
    await owner.getByRole('button', { name: 'Add staff' }).click();
    const form = owner.getByRole('dialog');
    await form.getByRole('textbox', { name: 'Name' }).fill(name);
    await form.getByRole('textbox', { name: 'Monthly salary (Rs)' }).fill('9000');
    await form.getByRole('button', { name: 'Add staff' }).click();
    await expect(form).toBeHidden();
  };

  const mistake = `Hari ${Date.now() % 100000}`;
  await add(mistake);
  await owner.getByText(mistake).click();
  await owner.getByRole('button', { name: 'Delete worker' }).click();
  await owner
    .getByRole('dialog', { name: `Delete ${mistake}?` })
    .getByRole('button', { name: 'Delete worker' })
    .click();
  await expect(owner.getByText(`${mistake} deleted`)).toBeVisible();
  await expect(owner.getByRole('row').filter({ hasText: mistake })).toHaveCount(0);

  // With an advance given, the record stays: no Delete, only "Still working here".
  const kept = `Sita ${Date.now() % 100000}`;
  await add(kept);
  await owner.goto('/staff/salary');
  const row = owner.getByRole('row').filter({ hasText: kept }).first();
  await row.getByRole('button', { name: `Actions for ${kept}` }).click();
  await owner.getByRole('menuitem', { name: 'Give advance' }).click();
  await owner.getByRole('dialog').getByRole('textbox', { name: 'Amount (Rs)' }).fill('100');
  await owner.getByRole('dialog').getByRole('button', { name: 'Give advance' }).click();
  await expect(owner.getByRole('dialog')).toBeHidden();
  await owner.goto('/staff/list');
  await owner.getByText(kept).click();
  const form = owner.getByRole('dialog');
  await expect(form.getByRole('switch', { name: 'Still working here' })).toBeVisible();
  await expect(form.getByRole('button', { name: 'Delete worker' })).toHaveCount(0);
});
