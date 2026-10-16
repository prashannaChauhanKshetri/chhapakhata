import dayjs from 'dayjs';

/** South Asian digit grouping (1,25,000.00), as used on Nepali bills. */
const moneyFormat = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const qtyFormat = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 });

export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

/** `125000` → `1,25,000.00` */
export function formatAmount(value: string | number | null | undefined): string {
  return moneyFormat.format(toNumber(value));
}

/** `125000` → `Rs. 1,25,000.00`; negatives as `-Rs. 4,500.00`. */
export function formatNPR(value: string | number | null | undefined): string {
  const n = toNumber(value);
  return `${n < 0 ? '-' : ''}Rs. ${moneyFormat.format(Math.abs(n))}`;
}

/** Compact form for KPI tiles: Rs. 1.25 L, Rs. 3.4 Cr. */
export function formatNPRCompact(value: string | number | null | undefined): string {
  const n = toNumber(value);
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1e7) return `${sign}Rs. ${(abs / 1e7).toFixed(2).replace(/\.?0+$/, '')} Cr`;
  if (abs >= 1e5) return `${sign}Rs. ${(abs / 1e5).toFixed(2).replace(/\.?0+$/, '')} L`;
  return formatNPR(n);
}

/** `12.50` → `12.5`, `8.00` → `8` */
export function formatQty(value: string | number | null | undefined): string {
  return qtyFormat.format(toNumber(value));
}

export function formatDate(value: string | Date | null | undefined): string {
  return value ? dayjs(value).format('D MMM YYYY') : '—';
}

export function formatDateTime(value: string | Date | null | undefined): string {
  return value ? dayjs(value).format('D MMM YYYY, h:mm A') : '—';
}

export function formatTime(value: string | Date | null | undefined): string {
  return value ? dayjs(value).format('h:mm A') : '—';
}

/** Short, human deadline label: "Today 4:00 PM", "Tomorrow", "Overdue 2 days". */
export function deadlineLabel(value: string | null | undefined, now = dayjs()): string {
  if (!value) return 'No deadline';
  const due = dayjs(value);
  if (due.isBefore(now)) {
    const days = now.startOf('day').diff(due.startOf('day'), 'day');
    return days <= 0
      ? `Overdue since ${due.format('h:mm A')}`
      : `Overdue ${days} day${days > 1 ? 's' : ''}`;
  }
  if (due.isSame(now, 'day')) return `Today ${due.format('h:mm A')}`;
  if (due.isSame(now.add(1, 'day'), 'day')) return `Tomorrow ${due.format('h:mm A')}`;
  return due.format('ddd D MMM, h:mm A');
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

/** Today in the browser's local time, as YYYY-MM-DD (Mantine date value format). */
export function todayISO(): string {
  return dayjs().format('YYYY-MM-DD');
}

/**
 * Ledger balance with its side: `1,200.00 Dr` (customer owes us), `300.00 Cr`
 * (advance with us), `0.00` when settled.
 */
export function formatBalance(value: string | number | null | undefined): string {
  const n = toNumber(value);
  if (n === 0) return moneyFormat.format(0);
  return `${moneyFormat.format(Math.abs(n))} ${n > 0 ? 'Dr' : 'Cr'}`;
}
