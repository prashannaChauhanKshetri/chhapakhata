import {
  AppShell,
  Avatar,
  Box,
  Burger,
  Button,
  Group,
  Menu,
  ScrollArea,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core';
import { useDisclosure, useNetwork } from '@mantine/hooks';
import { modals, ModalsProvider } from '@mantine/modals';
import { IconChevronDown, IconKey, IconLogout, IconPlus, IconWifiOff } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, NavLink, Outlet, useLocation } from 'react-router';

import { apiGet } from '@/api/http';
import type { DateConversion, ShopSettings } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { ChangePasswordForm } from '@/auth/ChangePasswordForm';
import { PageLoader } from '@/components/PageLoader';
import { formatDate } from '@/lib/format';
import { Perm } from '@/lib/permissions';

import classes from './AppLayout.module.css';
import { NAV } from './nav';

export function AppLayout() {
  const { t } = useTranslation();
  const { user, canAny, can, logout } = useAuth();
  const [opened, { toggle, close }] = useDisclosure(false);
  const location = useLocation();
  const network = useNetwork();

  const { data: today } = useQuery({
    queryKey: ['utils', 'today'],
    queryFn: () => apiGet<DateConversion>('/api/v1/utils/date/'),
    staleTime: 10 * 60_000,
  });
  const { data: shop } = useQuery({
    queryKey: ['settings', 'shop'],
    queryFn: () => apiGet<ShopSettings>('/api/v1/settings/shop/'),
    staleTime: 5 * 60_000,
  });

  const initials = (user?.full_name || user?.username || '?')
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const openChangePassword = () => {
    const id = modals.open({
      title: t('Change password'),
      children: <ChangePasswordForm onDone={() => modals.close(id)} />,
    });
  };

  return (
    // Dialogs render inside the router and auth providers, so their content can
    // use links, navigation and permissions like any page.
    <ModalsProvider labels={{ confirm: t('Confirm'), cancel: t('Cancel') }}>
      <AppShell
        header={{ height: 56 }}
        navbar={{ width: 240, breakpoint: 'md', collapsed: { mobile: !opened } }}
        padding={0}
      >
        <AppShell.Header className={classes.header}>
          <Group h="100%" px="md" justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap" miw={0}>
              <Burger
                opened={opened}
                onClick={toggle}
                hiddenFrom="md"
                size="sm"
                aria-label={t('Menu')}
              />
              <Text fw={600} size="sm" lineClamp={1}>
                {shop?.name ?? 'ChhapaKhata'}
              </Text>
              {today && (
                <Text size="sm" c="dimmed" visibleFrom="sm" lineClamp={1}>
                  {today.bs_long} · {formatDate(today.ad)}
                </Text>
              )}
            </Group>
            <Group gap="xs" wrap="nowrap">
              {can(Perm.ORDERS_MANAGE) && (
                <Button
                  component={Link}
                  to="/orders/new"
                  leftSection={<IconPlus size={16} />}
                  visibleFrom="xs"
                >
                  {t('New order')}
                </Button>
              )}
              <Menu position="bottom-end" width={220} shadow="md">
                <Menu.Target>
                  <UnstyledButton className={classes.userButton} aria-label={t('Account menu')}>
                    <Group gap={8} wrap="nowrap">
                      <Avatar size={30} radius="xl" color="slate" variant="filled">
                        {initials}
                      </Avatar>
                      <Box visibleFrom="sm" maw={140}>
                        <Text size="sm" fw={500} lineClamp={1}>
                          {user?.full_name || user?.username}
                        </Text>
                        <Text size="xs" c="dimmed" lineClamp={1}>
                          {user?.role_label}
                        </Text>
                      </Box>
                      <IconChevronDown size={14} />
                    </Group>
                  </UnstyledButton>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item leftSection={<IconKey size={16} />} onClick={openChangePassword}>
                    {t('Change password')}
                  </Menu.Item>
                  <Menu.Divider />
                  <Menu.Item leftSection={<IconLogout size={16} />} onClick={() => void logout()}>
                    {t('Sign out')}
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          </Group>
        </AppShell.Header>

        <AppShell.Navbar className={classes.navbar}>
          <AppShell.Section px="md" pt="md" pb="sm">
            <Text className={classes.brand}>ChhapaKhata</Text>
          </AppShell.Section>
          <AppShell.Section grow component={ScrollArea} px="sm">
            <Stack gap="md" pb="md">
              {NAV.map((section, index) => {
                const items = section.items.filter(
                  (item) => item.perms.length === 0 || canAny(...item.perms),
                );
                if (items.length === 0) return null;
                return (
                  <Stack key={section.label ?? index} gap={2}>
                    {section.label && (
                      <Text className={classes.sectionLabel}>{t(section.label)}</Text>
                    )}
                    {items.map((item) => (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        end={item.end}
                        onClick={close}
                        className={({ isActive }) =>
                          `${classes.link} ${isActive ? classes.linkActive : ''}`
                        }
                      >
                        <item.icon size={18} stroke={1.7} />
                        <span>{t(item.label)}</span>
                      </NavLink>
                    ))}
                  </Stack>
                );
              })}
            </Stack>
          </AppShell.Section>
          <AppShell.Section p="md" className={classes.navFooter}>
            <Text size="xs" c="slate.4">
              {today ? `${t('Fiscal year')} ${today.fiscal_year}` : ''}
            </Text>
          </AppShell.Section>
        </AppShell.Navbar>

        <AppShell.Main className={classes.main}>
          {!network.online && (
            <Group className={classes.offline} gap="xs" justify="center">
              <IconWifiOff size={16} />
              <Text size="sm">
                {t('This device is offline. Check the shop network connection.')}
              </Text>
            </Group>
          )}
          <Box className={classes.content}>
            <Suspense fallback={<PageLoader />} key={location.pathname}>
              <Outlet />
            </Suspense>
          </Box>
        </AppShell.Main>
      </AppShell>
    </ModalsProvider>
  );
}
