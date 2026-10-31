import { Box, Card, Group, SimpleGrid, Skeleton, Stack } from '@mantine/core';

/*
 * Placeholders shaped like the content that is loading, shown instead of a
 * spinner, so the page keeps its layout and does not jump when data arrives.
 */

const ROW_WIDTHS = ['92%', '78%', '86%', '70%', '88%', '64%', '82%', '74%'];

function Lines({ count, height = 12 }: { count: number; height?: number }) {
  return (
    <Stack gap={10}>
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} h={height} w={ROW_WIDTHS[i % ROW_WIDTHS.length]} radius="sm" />
      ))}
    </Stack>
  );
}

/** Table rows; used inside data tables while the first page loads. */
export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <Stack
      gap={0}
      w="100%"
      h="100%"
      bg="var(--mantine-color-body)"
      aria-busy="true"
      aria-label="Loading"
    >
      {Array.from({ length: rows }, (_, i) => (
        <Group
          key={i}
          gap="md"
          px="md"
          py={14}
          wrap="nowrap"
          style={{
            borderBottom:
              '1px solid light-dark(var(--mantine-color-gray-2), var(--mantine-color-dark-5))',
          }}
        >
          <Skeleton h={12} w="18%" radius="sm" />
          <Skeleton h={12} w="30%" radius="sm" />
          <Skeleton h={12} w="16%" radius="sm" visibleFrom="sm" />
          <Skeleton h={12} w="12%" radius="sm" ml="auto" />
        </Group>
      ))}
    </Stack>
  );
}

function HeaderSkeleton() {
  return (
    <Group justify="space-between" align="flex-end" mb="lg">
      <Stack gap={8}>
        <Skeleton h={26} w={220} radius="sm" />
        <Skeleton h={12} w={160} radius="sm" />
      </Stack>
      <Skeleton h={36} w={120} radius="md" visibleFrom="xs" />
    </Group>
  );
}

function StatSkeletons({ count = 3 }: { count?: number }) {
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: count }} mb="lg">
      {Array.from({ length: count }, (_, i) => (
        <Card key={i}>
          <Skeleton h={12} w="50%" radius="sm" mb={12} />
          <Skeleton h={28} w="70%" radius="sm" />
        </Card>
      ))}
    </SimpleGrid>
  );
}

/** A list page: heading, a few figures and a table. Default for lazy pages. */
export function PageSkeleton() {
  return (
    <Box aria-busy="true" aria-label="Loading">
      <HeaderSkeleton />
      <StatSkeletons />
      <Card padding={0}>
        <TableSkeleton rows={6} />
      </Card>
    </Box>
  );
}

/** A record page (order, invoice, customer, stock item): details cards and a table. */
export function DetailSkeleton() {
  return (
    <Box aria-busy="true" aria-label="Loading">
      <HeaderSkeleton />
      <SimpleGrid cols={{ base: 1, md: 2 }} mb="lg">
        <Card>
          <Skeleton h={14} w={120} radius="sm" mb="md" />
          <Lines count={4} />
        </Card>
        <Card>
          <Skeleton h={14} w={120} radius="sm" mb="md" />
          <Lines count={4} />
        </Card>
      </SimpleGrid>
      <Card padding={0}>
        <TableSkeleton rows={4} />
      </Card>
    </Box>
  );
}

/** A form page: labelled fields in cards. */
export function FormSkeleton({ sections = 2 }: { sections?: number }) {
  return (
    <Stack gap="lg" aria-busy="true" aria-label="Loading">
      {Array.from({ length: sections }, (_, s) => (
        <Card key={s}>
          <Skeleton h={14} w={140} radius="sm" mb="lg" />
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
            {Array.from({ length: 4 }, (_, i) => (
              <Stack key={i} gap={6}>
                <Skeleton h={10} w={90} radius="sm" />
                <Skeleton h={36} radius="md" />
              </Stack>
            ))}
          </SimpleGrid>
        </Card>
      ))}
    </Stack>
  );
}

/** The production board: stage columns with job cards. */
export function BoardSkeleton() {
  return (
    <Group
      align="flex-start"
      gap="md"
      wrap="nowrap"
      style={{ overflow: 'hidden' }}
      aria-busy="true"
    >
      {[3, 2, 4, 1, 2].map((cards, c) => (
        <Stack key={c} gap="sm" miw={240} style={{ flex: 1 }}>
          <Skeleton h={14} w="60%" radius="sm" />
          {Array.from({ length: cards }, (_, i) => (
            <Card key={i} padding="sm">
              <Skeleton h={12} w="50%" radius="sm" mb={10} />
              <Skeleton h={10} w="85%" radius="sm" mb={8} />
              <Skeleton h={6} radius="xl" />
            </Card>
          ))}
        </Stack>
      ))}
    </Group>
  );
}

/** A report: summary figures and a table. */
export function ReportSkeleton() {
  return (
    <Box aria-busy="true" aria-label="Loading">
      <StatSkeletons count={4} />
      <Card padding={0}>
        <TableSkeleton rows={8} />
      </Card>
    </Box>
  );
}

/** The whole app while it checks who is signed in: top bar, menu and a page. */
export function AppSkeleton() {
  return (
    <Box mih="100vh" aria-busy="true" aria-label="Loading">
      <Group
        h={56}
        px="md"
        justify="space-between"
        style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
      >
        <Skeleton h={28} w={150} radius="sm" />
        <Skeleton h={30} w={30} circle />
      </Group>
      <Group align="flex-start" gap={0} wrap="nowrap">
        <Stack
          gap="sm"
          p="md"
          w={240}
          visibleFrom="sm"
          style={{ borderRight: '1px solid var(--mantine-color-default-border)' }}
          mih="calc(100vh - 56px)"
        >
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} h={20} w={`${70 + ((i * 7) % 25)}%`} radius="sm" />
          ))}
        </Stack>
        <Box p="lg" style={{ flex: 1 }}>
          <PageSkeleton />
        </Box>
      </Group>
    </Box>
  );
}
