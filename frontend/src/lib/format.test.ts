import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';

import {
  deadlineLabel,
  formatAmount,
  formatNPR,
  formatNPRCompact,
  formatQty,
  toNumber,
} from './format';

describe('money formatting', () => {
  it('uses South Asian (lakh) grouping', () => {
    expect(formatAmount(125000)).toBe('1,25,000.00');
    expect(formatNPR('12500000.5')).toBe('Rs. 1,25,00,000.50');
    expect(formatNPR(-4500)).toBe('-Rs. 4,500.00');
  });

  it('treats blanks and junk as zero', () => {
    expect(toNumber('')).toBe(0);
    expect(toNumber(null)).toBe(0);
    expect(toNumber('abc')).toBe(0);
    expect(formatNPR(undefined)).toBe('Rs. 0.00');
  });

  it('compacts large values for tiles', () => {
    expect(formatNPRCompact(99999)).toBe('Rs. 99,999.00');
    expect(formatNPRCompact(125000)).toBe('Rs. 1.25 L');
    expect(formatNPRCompact(30000000)).toBe('Rs. 3 Cr');
  });

  it('drops needless decimals on quantities', () => {
    expect(formatQty('8.00')).toBe('8');
    expect(formatQty('12.50')).toBe('12.5');
    expect(formatQty(1640)).toBe('1,640');
  });
});

describe('deadlineLabel', () => {
  const now = dayjs('2026-10-15T10:00:00');

  it('describes today, tomorrow and overdue', () => {
    expect(deadlineLabel('2026-10-15T16:00:00', now)).toBe('Today 4:00 PM');
    expect(deadlineLabel('2026-10-16T17:00:00', now)).toBe('Tomorrow 5:00 PM');
    expect(deadlineLabel('2026-10-13T17:00:00', now)).toBe('Overdue 2 days');
    expect(deadlineLabel('2026-10-15T09:00:00', now)).toBe('Overdue since 9:00 AM');
    expect(deadlineLabel(null, now)).toBe('No deadline');
  });
});
