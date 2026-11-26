import { Anchor, Button, Group, Stack, Text, Title } from '@mantine/core';
import { IconArrowLeft, IconLayoutDashboard } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router';

import { useAuth } from '@/auth/AuthContext';
import { Perm } from '@/lib/permissions';

import classes from './NotFoundPage.module.css';

const CMYK = ['#00AEEF', '#EC008C', '#FFF200', '#231F20'];

/**
 * A page that does not exist, told the print shop's way: a misprinted proof with
 * its job ticket, stamped "not found".
 */
export default function NotFoundPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { can } = useAuth();

  const shortcuts = [
    { to: '/orders', label: t('Orders'), show: can(Perm.ORDERS_VIEW) },
    { to: '/customers', label: t('Customers'), show: can(Perm.CUSTOMERS_VIEW) },
    { to: '/invoices', label: t('Invoices'), show: can(Perm.INVOICES_VIEW) },
  ].filter((s) => s.show);

  return (
    <div className={classes.page}>
      <Stack gap="lg" align="center" w="100%">
        <div className={classes.press} aria-hidden="true">
          <div className={classes.slot} />
          <div className={classes.feed}>
            <div className={classes.sheet}>
              <span className={`${classes.crop} ${classes.tl}`} />
              <span className={`${classes.crop} ${classes.tr}`} />
              <span className={`${classes.crop} ${classes.bl}`} />
              <span className={`${classes.crop} ${classes.br}`} />
              <svg className={classes.registration} width="18" height="18" viewBox="0 0 18 18">
                <circle cx="9" cy="9" r="5" fill="none" stroke="currentColor" />
                <path d="M9 0v18M0 9h18" stroke="currentColor" />
              </svg>
              <div className={classes.cmyk}>
                {CMYK.map((c) => (
                  <span key={c} style={{ background: c }} />
                ))}
              </div>

              <div className={classes.ticket}>
                <div className={classes.ticketHead}>
                  <span>JOB TICKET</span>
                  <span>JOB-404</span>
                </div>
                <dl style={{ margin: 0 }}>
                  <div className={classes.row}>
                    <dt>{t('Page')}</dt>
                    <dd className={classes.path}>{pathname}</dd>
                  </div>
                  <div className={classes.row}>
                    <dt>{t('Media')}</dt>
                    <dd>{t('Thin air')}</dd>
                  </div>
                  <div className={classes.row}>
                    <dt>{t('Size')}</dt>
                    <dd>0 × 0 ft (0 sq ft)</dd>
                  </div>
                  <div className={classes.row}>
                    <dt>{t('Stage')}</dt>
                    <dd>{t('Lost somewhere in the roll')}</dd>
                  </div>
                </dl>
              </div>

              <div className={classes.stamp}>
                <div className={classes.stampMain}>NOT FOUND · 404</div>
                <div className={classes.stampSub}>पाना भेटिएन</div>
              </div>
            </div>
          </div>
        </div>

        <Stack gap={6} align="center" maw={440} ta="center">
          <Title order={1}>{t('This page didn’t come off the press')}</Title>
          <Text c="dimmed">
            {t(
              'The address may be mistyped, or what was here has moved. Nothing is lost: your orders and accounts are where you left them.',
            )}
          </Text>
        </Stack>

        <Group gap="xs" justify="center">
          <Button
            variant="default"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => void navigate(-1)}
          >
            {t('Go back')}
          </Button>
          <Button component={Link} to="/" leftSection={<IconLayoutDashboard size={16} />}>
            {t('Dashboard')}
          </Button>
        </Group>
        {shortcuts.length > 0 && (
          <Text size="sm" c="dimmed">
            {t('Or open')}{' '}
            {shortcuts.map((s, i) => (
              <span key={s.to}>
                <Anchor component={Link} to={s.to} size="sm">
                  {s.label}
                </Anchor>
                {i < shortcuts.length - 1 ? ' · ' : ''}
              </span>
            ))}
          </Text>
        )}
      </Stack>
    </div>
  );
}
