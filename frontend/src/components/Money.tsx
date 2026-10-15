import { Text, type TextProps } from '@mantine/core';

import { formatAmount, formatNPR, toNumber } from '@/lib/format';

interface MoneyProps extends TextProps {
  value: string | number | null | undefined;
  /** Show the "Rs." prefix (default true). */
  prefix?: boolean;
  /** Colour negative values (advances/credits) and dues. */
  tone?: 'plain' | 'due';
}

/** Money with tabular digits and South Asian grouping. */
export function Money({ value, prefix = true, tone = 'plain', ...props }: MoneyProps) {
  const n = toNumber(value);
  const color = tone === 'due' ? (n > 0 ? 'red.7' : n < 0 ? 'green.7' : undefined) : undefined;
  return (
    <Text span className="num" c={color} {...props}>
      {prefix ? formatNPR(n) : formatAmount(n)}
    </Text>
  );
}
