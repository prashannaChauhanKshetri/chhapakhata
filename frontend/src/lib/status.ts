/** Labels and colours for statuses and production stages.
 * Colours carry meaning only; everything else stays slate. */

export interface StatusStyle {
  label: string;
  color: string;
}

export const STAGES: Record<number, StatusStyle & { short: string }> = {
  0: { label: 'Cancelled', short: 'Cancelled', color: 'red' },
  1: { label: 'Design pending / Proof sent', short: 'Design', color: 'slate' },
  2: { label: 'Ready for print', short: 'Ready for print', color: 'blue' },
  3: { label: 'Printing', short: 'Printing', color: 'amber' },
  4: { label: 'Finishing / Framing', short: 'Finishing', color: 'violet' },
  5: { label: 'Ready for collection', short: 'Ready', color: 'green' },
  6: { label: 'Delivered', short: 'Delivered', color: 'slate' },
};

export const BOARD_STAGES = [1, 2, 3, 4, 5, 6] as const;

export const ORDER_STATUS: Record<string, StatusStyle> = {
  quotation: { label: 'Quotation', color: 'slate' },
  confirmed: { label: 'Confirmed', color: 'blue' },
  in_production: { label: 'In production', color: 'amber' },
  ready: { label: 'Ready', color: 'green' },
  delivered: { label: 'Delivered', color: 'slate' },
  cancelled: { label: 'Cancelled', color: 'red' },
};

export const INVOICE_STATUS: Record<string, StatusStyle> = {
  issued: { label: 'Issued', color: 'green' },
  cancelled: { label: 'Cancelled', color: 'red' },
};

export const PAYMENT_STATUS: Record<string, StatusStyle> = {
  valid: { label: 'Valid', color: 'green' },
  void: { label: 'Void', color: 'red' },
};

export const BACKUP_STATUS: Record<string, StatusStyle> = {
  running: { label: 'Running', color: 'blue' },
  success: { label: 'Succeeded', color: 'green' },
  failed: { label: 'Failed', color: 'red' },
};

export const PAYMENT_MODES = [
  { value: 'cash', label: 'Cash' },
  { value: 'wallet', label: 'QR / Wallet' },
  { value: 'bank', label: 'Bank transfer' },
  { value: 'cheque', label: 'Cheque' },
];

export const WALLETS = [
  { value: 'esewa', label: 'eSewa' },
  { value: 'khalti', label: 'Khalti' },
  { value: 'fonepay', label: 'Fonepay' },
  { value: 'other_qr', label: 'Other QR' },
];

export const UNITS = [
  { value: 'ft', label: 'ft' },
  { value: 'in', label: 'in' },
  { value: 'cm', label: 'cm' },
];
