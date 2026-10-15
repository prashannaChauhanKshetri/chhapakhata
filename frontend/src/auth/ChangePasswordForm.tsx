import { Button, Group, PasswordInput, Stack } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { handleFormError, notifySuccess } from '@/lib/forms';

export function ChangePasswordForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: { current_password: '', new_password: '', confirm: '' },
    validate: {
      current_password: (v) => (v ? null : t('Enter your current password')),
      new_password: (v) => (v.length >= 8 ? null : t('Use at least 8 characters')),
      confirm: (v, values) => (v === values.new_password ? null : t('Passwords do not match')),
    },
  });

  const submit = form.onSubmit(async ({ current_password, new_password }) => {
    setBusy(true);
    try {
      await unwrap(
        api.POST('/api/v1/auth/change-password/', { body: { current_password, new_password } }),
      );
      notifySuccess(t('Your password was changed.'));
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
        <PasswordInput
          label={t('Current password')}
          autoComplete="current-password"
          data-autofocus
          {...form.getInputProps('current_password')}
        />
        <PasswordInput
          label={t('New password')}
          autoComplete="new-password"
          {...form.getInputProps('new_password')}
        />
        <PasswordInput
          label={t('Repeat new password')}
          autoComplete="new-password"
          {...form.getInputProps('confirm')}
        />
        <Group justify="flex-end" mt="xs">
          <Button variant="default" onClick={onDone}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {t('Change password')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
