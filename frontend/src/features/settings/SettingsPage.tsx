import { ScrollArea, Tabs } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Navigate, useNavigate, useParams } from 'react-router';

import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/PageHeader';
import { Perm, type PermName } from '@/lib/permissions';

import { ActivityTab } from './ActivityTab';
import { BackupsTab } from './BackupsTab';
import { RateCardTab } from './RateCardTab';
import { ShopSettingsTab } from './ShopSettingsTab';
import { UsersTab } from './UsersTab';

const TABS: { value: string; label: string; perms: PermName[]; render: () => React.ReactNode }[] = [
  {
    value: 'shop',
    label: 'Shop',
    perms: [Perm.SETTINGS_MANAGE],
    render: () => <ShopSettingsTab />,
  },
  {
    value: 'rate-card',
    label: 'Rate card',
    perms: [Perm.CATALOG_MANAGE],
    render: () => <RateCardTab />,
  },
  { value: 'users', label: 'Users', perms: [Perm.USERS_MANAGE], render: () => <UsersTab /> },
  {
    value: 'backups',
    label: 'Backups & export',
    perms: [Perm.SYSTEM_BACKUP, Perm.SETTINGS_MANAGE],
    render: () => <BackupsTab />,
  },
  {
    value: 'activity',
    label: 'Activity log',
    perms: [Perm.AUDIT_VIEW],
    render: () => <ActivityTab />,
  },
];

export default function SettingsPage() {
  const { t } = useTranslation();
  const { tab } = useParams();
  const navigate = useNavigate();
  const { canAny } = useAuth();
  const visible = TABS.filter((x) => canAny(...x.perms));
  const current = visible.find((x) => x.value === tab);
  if (!current)
    return visible[0] ? <Navigate to={`/settings/${visible[0].value}`} replace /> : null;

  return (
    <>
      <PageHeader
        title={t('Settings')}
        description={t('Shop details, prices, staff accounts and data safety.')}
      />
      <Tabs
        value={current.value}
        onChange={(v) => v && navigate(`/settings/${v}`)}
        keepMounted={false}
      >
        <ScrollArea type="never" mb="lg">
          <Tabs.List style={{ flexWrap: 'nowrap' }}>
            {visible.map((x) => (
              <Tabs.Tab key={x.value} value={x.value}>
                {t(x.label)}
              </Tabs.Tab>
            ))}
          </Tabs.List>
        </ScrollArea>
        {visible.map((x) => (
          <Tabs.Panel key={x.value} value={x.value}>
            {x.render()}
          </Tabs.Panel>
        ))}
      </Tabs>
    </>
  );
}
