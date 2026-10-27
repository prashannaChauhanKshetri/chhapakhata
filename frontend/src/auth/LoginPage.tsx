import {
  Alert,
  Box,
  Button,
  Paper,
  PasswordInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import {
  IconAlertCircle,
  IconBuildingWarehouse,
  IconClipboardList,
  IconFileInvoice,
  IconLayoutKanban,
  IconWifi,
} from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, ensureCsrfCookie, unwrap } from '@/api/client';
import { errorMessage } from '@/api/errors';
import { Logo, LogoMark } from '@/components/Logo';
import { TextSizeControl } from '@/components/TextSizeControl';

import { useAuth } from './AuthContext';
import classes from './LoginPage.module.css';

const FEATURES = [
  { icon: IconClipboardList, title: 'Orders', text: 'Sq ft pricing, quotations, last rates' },
  { icon: IconLayoutKanban, title: 'Production', text: 'Drag jobs from design to delivery' },
  { icon: IconBuildingWarehouse, title: 'Stock', text: 'Every roll, every sq ft used' },
  { icon: IconFileInvoice, title: 'Billing', text: 'Invoices, payments, customer dues' },
];

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
        <div className={classes.brandContent}>
          <Logo size={52} onDark />
          <Title order={1} c="white" fz={32} lh={1.2} mt={36}>
            {t('Your print shop, from counter to collection')}
          </Title>
          <Text c="slate.3" mt="sm" maw={420}>
            {t('Orders, production, stock, billing and customer dues in one place.')}
          </Text>
          <SimpleGrid cols={2} spacing="sm" mt={32}>
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className={classes.feature}>
                <span className={classes.featureIcon} aria-hidden="true">
                  <Icon size={18} stroke={1.75} />
                </span>
                <div>
                  <Text size="sm" fw={600} c="white">
                    {t(title)}
                  </Text>
                  <Text size="xs" c="slate.4" mt={2}>
                    {t(text)}
                  </Text>
                </div>
              </div>
            ))}
          </SimpleGrid>
        </div>
        <div className={classes.watermark} aria-hidden="true">
          <LogoMark size={320} />
        </div>
        <div className={classes.footnote}>
          <IconWifi size={14} />
          {t('Runs on the shop network and keeps working without internet.')}
        </div>
      </Box>
      <Box className={classes.formPanel}>
        <Box className={classes.textSize}>
          <TextSizeControl withLabel={false} />
        </Box>
        <Box hiddenFrom="md" mb="lg" mt="xl">
          <Logo size={40} />
        </Box>
        <Paper className={classes.card} withBorder p="xl">
          <form onSubmit={submit} noValidate>
            <Stack gap="md">
              <div>
                <Title order={2}>{t('Welcome back')}</Title>
                <Text c="dimmed" size="sm" mt={4}>
                  {t('Sign in with your personal staff account.')}
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
