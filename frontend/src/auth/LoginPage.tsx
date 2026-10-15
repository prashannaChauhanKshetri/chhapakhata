import {
  Alert,
  Box,
  Button,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconAlertCircle } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, ensureCsrfCookie, unwrap } from '@/api/client';
import { errorMessage } from '@/api/errors';

import { useAuth } from './AuthContext';
import classes from './LoginPage.module.css';

export function LoginPage() {
  const { t } = useTranslation();
  const { setUser } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const form = useForm({
    initialValues: { username: '', password: '' },
    validate: {
      username: (v) => (v.trim() ? null : t('Enter your username')),
      password: (v) => (v ? null : t('Enter your password')),
    },
  });

  const submit = form.onSubmit(async (values) => {
    setError(null);
    setSubmitting(true);
    try {
      await ensureCsrfCookie();
      const me = await unwrap(
        api.POST('/api/v1/auth/login/', {
          body: { username: values.username.trim(), password: values.password },
        }),
      );
      setUser(me);
    } catch (err) {
      setError(errorMessage(err));
      form.setFieldValue('password', '');
    } finally {
      setSubmitting(false);
    }
  });

  return (
    <Box className={classes.page}>
      <Box className={classes.brandPanel} visibleFrom="md">
        <Stack gap="xs">
          <Text className={classes.eyebrow}>ChhapaKhata</Text>
          <Title order={1} c="white" fz={30}>
            {t('Print shop management')}
          </Title>
          <Text c="slate.3" maw={360}>
            {t('Orders, production, stock, billing and customer dues in one place.')}
          </Text>
        </Stack>
      </Box>
      <Box className={classes.formPanel}>
        <Paper className={classes.card} withBorder p="xl">
          <form onSubmit={submit} noValidate>
            <Stack gap="md">
              <div>
                <Title order={2}>{t('Sign in')}</Title>
                <Text c="dimmed" size="sm" mt={4}>
                  {t('Use your personal staff account.')}
                </Text>
              </div>
              {error && (
                <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />}>
                  {error}
                </Alert>
              )}
              <TextInput
                label={t('Username')}
                autoComplete="username"
                autoFocus
                {...form.getInputProps('username')}
              />
              <PasswordInput
                label={t('Password')}
                autoComplete="current-password"
                {...form.getInputProps('password')}
              />
              <Button type="submit" loading={submitting} fullWidth size="md">
                {t('Sign in')}
              </Button>
              <Text size="xs" c="dimmed" ta="center">
                {t('Forgot your password? Ask the owner to reset it.')}
              </Text>
            </Stack>
          </form>
        </Paper>
      </Box>
    </Box>
  );
}
