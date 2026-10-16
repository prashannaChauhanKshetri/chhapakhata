import { Text, type TextProps } from '@mantine/core';

import { formatBalance, toNumber } from '@/lib/format';

/** A ledger balance shown as Dr (due) or Cr (advance), with tabular digits. */
export function Balance({
  value,
  ...props
}: TextProps & { value: string | number | null | undefined }) {
  const n = toNumber(value);
  return (
    <Text span className="num" c={n < 0 ? 'green.8' : undefined} {...props}>
      {formatBalance(n)}
    </Text>
  );
}
