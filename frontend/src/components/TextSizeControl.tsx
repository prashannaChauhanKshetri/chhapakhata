import { SegmentedControl, Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { setTextSize, TEXT_SIZES, type TextSize, useTextSize } from '@/app/textSize';

/** Normal / Large / Extra large, shown as A, A+, A++ with full names for screen readers. */
export function TextSizeControl({ withLabel = true }: { withLabel?: boolean }) {
  const { t } = useTranslation();
  const size = useTextSize();
  const short: Record<TextSize, string> = { normal: 'A', large: 'A+', larger: 'A++' };
  return (
    <Stack gap={4}>
      {withLabel && (
        <Text size="xs" c="dimmed" fw={500} id="text-size-label">
          {t('Text size')}
        </Text>
      )}
      <SegmentedControl
        size="xs"
        fullWidth
        value={size}
        onChange={(v) => setTextSize(v as TextSize)}
        aria-labelledby={withLabel ? 'text-size-label' : undefined}
        aria-label={withLabel ? undefined : t('Text size')}
        data={TEXT_SIZES.map((s) => ({
          value: s.value,
          label: (
            <span title={t(s.label)} aria-label={t(s.label)}>
              {short[s.value]}
            </span>
          ),
        }))}
      />
    </Stack>
  );
}
