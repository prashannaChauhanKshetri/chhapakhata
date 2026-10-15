import { Card, Group, SimpleGrid, Stack, Text, ThemeIcon } from '@mantine/core';
import {
  IconCalendarStats,
  IconCash,
  IconChevronRight,
  IconClipboardData,
  IconFileAnalytics,
  IconPackage,
  IconPrinter,
  IconUsers,
  type Icon,
} from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { apiGet } from '@/api/http';
import type { ReportInfo } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { PageLoader } from '@/components/PageLoader';
import { QueryError } from '@/components/QueryError';

const META: Record<string, { icon: Icon; description: string }> = {
  'daily-sales': {
    icon: IconCalendarStats,
    description: 'Orders, invoices and collection by payment mode for one day.',
  },
  'monthly-sales': {
    icon: IconFileAnalytics,
    description: 'Sales by day and by media type for a period (defaults to this BS month).',
  },
  'pending-dues': {
    icon: IconUsers,
    description: 'Customers who owe money, oldest first, with ageing.',
  },
  collections: {
    icon: IconCash,
    description: 'Payments received in a period, by mode and by staff.',
  },
  'material-vs-sales': {
    icon: IconClipboardData,
    description: 'Sq ft used from rolls compared with sq ft billed, and wastage.',
  },
  'operator-log': { icon: IconPrinter, description: 'Jobs and sq ft printed per operator.' },
  stock: { icon: IconPackage, description: 'Current stock, roll balances and the low-stock list.' },
};

export default function ReportsPage() {
  const { t } = useTranslation();
  const { data, error, refetch } = useQuery({
    queryKey: ['reports'],
    queryFn: () => apiGet<ReportInfo[]>('/api/v1/reports/'),
  });
  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;
  if (!data) return <PageLoader />;
  return (
    <>
      <PageHeader
        title={t('Reports')}
        description={t('Every report can be printed or downloaded as Excel or PDF.')}
      />
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
        {data.map((report) => {
          const meta = META[report.slug] ?? { icon: IconFileAnalytics, description: '' };
          return (
            <Card
              key={report.slug}
              component={Link}
              to={`/reports/${report.slug}`}
              style={{ textDecoration: 'none' }}
            >
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <Group gap="sm" wrap="nowrap" align="flex-start">
                  <ThemeIcon variant="light" color="slate" size={38} radius="md">
                    <meta.icon size={20} stroke={1.6} />
                  </ThemeIcon>
                  <Stack gap={2}>
                    <Text fw={600}>{t(report.title)}</Text>
                    <Text size="sm" c="dimmed">
                      {t(meta.description)}
                    </Text>
                  </Stack>
                </Group>
                <IconChevronRight size={18} color="var(--ck-decor)" />
              </Group>
            </Card>
          );
        })}
      </SimpleGrid>
    </>
  );
}
