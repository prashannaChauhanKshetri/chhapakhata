import { Button, Group, Stack, Text, Textarea } from '@mantine/core';
import { modals } from '@mantine/modals';
import { useState } from 'react';

import { errorMessage } from '@/api/errors';

interface ReasonFormProps {
  message: string;
  label: string;
  confirmLabel: string;
  danger: boolean;
  onConfirm: (reason: string) => Promise<unknown>;
  onDone: () => void;
}

function ReasonForm({ message, label, confirmLabel, danger, onConfirm, onDone }: ReasonFormProps) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const tooShort = reason.trim().length < 5;

  const submit = async () => {
    if (tooShort) {
      setError('Write a short reason (at least 5 characters).');
      return;
    }
    setBusy(true);
    try {
      await onConfirm(reason.trim());
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap="md">
      <Text size="sm">{message}</Text>
      <Textarea
        label={label}
        value={reason}
        onChange={(e) => {
          setReason(e.currentTarget.value);
          setError(null);
        }}
        error={error}
        minRows={2}
        maxLength={255}
        data-autofocus
      />
      <Group justify="flex-end" gap="xs">
        <Button variant="default" onClick={onDone} disabled={busy}>
          Keep it
        </Button>
        <Button color={danger ? 'red' : undefined} onClick={submit} loading={busy}>
          {confirmLabel}
        </Button>
      </Group>
    </Stack>
  );
}

interface OpenReasonModalOptions {
  title: string;
  message: string;
  label?: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: (reason: string) => Promise<unknown>;
}

/** Confirm an irreversible action that must record a reason (cancel, void, adjust). */
export function openReasonModal(options: OpenReasonModalOptions): void {
  const id = modals.open({
    title: options.title,
    children: (
      <ReasonForm
        message={options.message}
        label={options.label ?? 'Reason'}
        confirmLabel={options.confirmLabel}
        danger={options.danger ?? true}
        onConfirm={options.onConfirm}
        onDone={() => modals.close(id)}
      />
    ),
  });
}
