import i18n from './i18n';

describe('counted messages', () => {
  it('uses the singular for one', () => {
    expect(i18n.t('{{count}} invoices', { count: 1 })).toBe('1 invoice');
    expect(i18n.t('{{count}} invoices', { count: 3 })).toBe('3 invoices');
    expect(i18n.t('{{count}} items', { count: 1 })).toBe('1 item');
  });
});
