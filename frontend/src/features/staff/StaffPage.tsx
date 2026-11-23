import { ScrollArea, Tabs } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Navigate, useNavigate, useParams } from 'react-router';

import { PageHeader } from '@/components/PageHeader';

import { AttendanceTab } from './AttendanceTab';
import { SalaryTab } from './SalaryTab';
import { StaffListTab } from './StaffListTab';

const TABS = [
  { value: 'attendance', label: 'Attendance', render: () => <AttendanceTab /> },
  { value: 'salary', label: 'Salary', render: () => <SalaryTab /> },
  { value: 'list', label: 'Staff', render: () => <StaffListTab /> },
];

/** Staff attendance, advances and monthly salary. Owner only. */
export default function StaffPage() {
  const { t } = useTranslation();
  const { tab } = useParams();
  const navigate = useNavigate();
  const current = TABS.find((x) => x.value === tab);
  if (!current) return <Navigate to="/staff/attendance" replace />;

  return (
    <>
      <PageHeader
        title={t('Staff & salary')}
        description={t(
          'Mark who is absent each day. An absent day takes off one day of pay; working on a Saturday adds one.',
        )}
      />
      <Tabs
        value={current.value}
        onChange={(v) => v && navigate(`/staff/${v}`)}
        keepMounted={false}
      >
        <ScrollArea type="never" mb="lg">
          <Tabs.List style={{ flexWrap: 'nowrap' }}>
            {TABS.map((x) => (
              <Tabs.Tab key={x.value} value={x.value}>
                {t(x.label)}
              </Tabs.Tab>
            ))}
          </Tabs.List>
        </ScrollArea>
        {TABS.map((x) => (
          <Tabs.Panel key={x.value} value={x.value}>
            {x.render()}
          </Tabs.Panel>
        ))}
      </Tabs>
    </>
  );
}
