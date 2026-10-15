import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Group,
  Menu,
  NumberInput,
  PasswordInput,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import {
  IconDotsVertical,
  IconInfoCircle,
  IconKey,
  IconPencil,
  IconUserPlus,
} from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { DataTable } from 'mantine-datatable';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { Paginated, User } from '@/api/types';
import { SectionCard } from '@/components/SectionCard';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { formatDateTime, toNumber } from '@/lib/format';
import { ROLE_LABELS } from '@/lib/permissions';

const ROLES = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }));

function UserForm({ user, onDone }: { user?: User; onDone: () => void }) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: {
      username: user?.username ?? '',
      first_name: user?.first_name ?? '',
      last_name: user?.last_name ?? '',
      phone: user?.phone ?? '',
      role: user?.role ?? 'front_desk',
      max_discount_percent:
        user?.max_discount_percent === null || user?.max_discount_percent === undefined
          ? ('' as number | string)
          : toNumber(user.max_discount_percent),
      is_active: user?.is_active ?? true,
      password: '',
    },
    validate: {
      username: (v) =>
        /^[\w.@+-]{3,150}$/.test(v) ? null : 'Use 3+ letters, numbers or . @ + - _',
      first_name: (v) => (v.trim() ? null : 'Enter the first name'),
      password: (v) => (!user && v.length < 8 ? 'Use at least 8 characters' : null),
    },
  });
  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    const body = {
      ...values,
      role: values.role as 'owner',
      max_discount_percent:
        values.max_discount_percent === '' ? null : String(values.max_discount_percent),
      ...(values.password ? { password: values.password } : { password: undefined }),
    };
    try {
      if (user)
        await unwrap(api.PATCH('/api/v1/users/{id}/', { params: { path: { id: user.id } }, body }));
      else
        await unwrap(api.POST('/api/v1/users/', { body: { ...body, password: values.password } }));
      await client.invalidateQueries({ queryKey: ['users'] });
      notifySuccess(user ? 'User updated' : 'User added');
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });
  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        <SimpleGrid cols={2} spacing="sm">
          <TextInput label="First name" data-autofocus {...form.getInputProps('first_name')} />
          <TextInput label="Last name" {...form.getInputProps('last_name')} />
        </SimpleGrid>
        <SimpleGrid cols={2} spacing="sm">
          <TextInput
            label="Username"
            description="Used to sign in"
            disabled={!!user}
            {...form.getInputProps('username')}
          />
          <TextInput label="Phone" {...form.getInputProps('phone')} />
        </SimpleGrid>
        <Select label="Role" data={ROLES} {...form.getInputProps('role')} />
        {form.values.role === 'front_desk' && (
          <NumberInput
            label="Discount limit %"
            description="Leave empty to use the shop default."
            min={0}
            max={100}
            decimalScale={2}
            {...form.getInputProps('max_discount_percent')}
          />
        )}
        {!user && (
          <PasswordInput
            label="Password"
            description="At least 8 characters; not only numbers"
            {...form.getInputProps('password')}
          />
        )}
        {user && (
          <Switch
            label="Active"
            description="Inactive users cannot sign in. History keeps their name."
            {...form.getInputProps('is_active', { type: 'checkbox' })}
          />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {user ? 'Save' : 'Add user'}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function ResetPasswordForm({ user, onDone }: { user: User; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: { new_password: '' },
    validate: { new_password: (v) => (v.length >= 8 ? null : 'Use at least 8 characters') },
  });
  const submit = form.onSubmit(async ({ new_password }) => {
    setBusy(true);
    try {
      await unwrap(
        api.POST('/api/v1/users/{id}/reset-password/', {
          params: { path: { id: user.id } },
          body: { new_password },
        }),
      );
      notifySuccess(`Password reset for ${user.username}`);
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });
  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          Give the new password to {user.full_name || user.username} in person and ask them to
          change it after signing in.
        </Text>
        <PasswordInput
          label="New password"
          data-autofocus
          {...form.getInputProps('new_password')}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Reset password
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function UsersTab() {
  const { t } = useTranslation();
  const { data, isPending } = useQuery({
    queryKey: ['users'],
    queryFn: () => apiGet<Paginated<User>>('/api/v1/users/', { page_size: 100 }),
  });
  const users = data?.results ?? [];
  const active = users.filter((u) => u.is_active).length;
  const open = (title: string, node: (close: () => void) => React.ReactNode) => {
    const id = modals.open({ title, children: node(() => modals.close(id)) });
  };

  return (
    <Stack gap="lg">
      <Alert color="slate" variant="light" icon={<IconInfoCircle size={16} />}>
        {t('Your plan includes up to 5 active accounts. {{n}} in use.', { n: active })}
      </Alert>
      <SectionCard
        title={t('Staff accounts')}
        flush
        actions={
          <Button
            size="xs"
            leftSection={<IconUserPlus size={14} />}
            onClick={() => open(t('New user'), (close) => <UserForm onDone={close} />)}
          >
            {t('Add user')}
          </Button>
        }
      >
        <DataTable<User>
          minHeight={120}
          fetching={isPending}
          records={users}
          rowStyle={(u) => (!u.is_active ? { opacity: 0.55 } : undefined)}
          columns={[
            {
              accessor: 'full_name',
              title: t('Name'),
              render: (u) => (
                <div>
                  <Text size="sm" fw={500}>
                    {u.full_name || u.username}
                  </Text>
                  <Text size="xs" c="dimmed">
                    @{u.username}
                    {u.phone ? ` · ${u.phone}` : ''}
                  </Text>
                </div>
              ),
            },
            {
              accessor: 'role',
              title: t('Role'),
              render: (u) => (
                <Badge
                  color={u.role === 'owner' ? 'slate' : u.role === 'operator' ? 'violet' : 'blue'}
                >
                  {u.role_label}
                </Badge>
              ),
            },
            {
              accessor: 'last_login',
              title: t('Last sign-in'),
              visibleMediaQuery: '(min-width: 48em)',
              render: (u) => formatDateTime(u.last_login),
            },
            {
              accessor: 'is_active',
              title: t('Status'),
              render: (u) =>
                u.is_active ? (
                  <Badge color="green">{t('Active')}</Badge>
                ) : (
                  <Badge color="slate">{t('Inactive')}</Badge>
                ),
            },
            {
              accessor: 'actions',
              title: '',
              width: 48,
              render: (u) => (
                <Menu position="bottom-end" withinPortal>
                  <Menu.Target>
                    <ActionIcon aria-label={t('User actions')}>
                      <IconDotsVertical size={16} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item
                      leftSection={<IconPencil size={16} />}
                      onClick={() =>
                        open(t('Edit {{name}}', { name: u.username }), (close) => (
                          <UserForm user={u} onDone={close} />
                        ))
                      }
                    >
                      {t('Edit')}
                    </Menu.Item>
                    <Menu.Item
                      leftSection={<IconKey size={16} />}
                      onClick={() =>
                        open(t('Reset password'), (close) => (
                          <ResetPasswordForm user={u} onDone={close} />
                        ))
                      }
                    >
                      {t('Reset password')}
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              ),
            },
          ]}
        />
      </SectionCard>
    </Stack>
  );
}
