import { notifications } from '@mantine/notifications';

import { ApiError, errorMessage } from '@/api/errors';

interface FormLike {
  setErrors: (errors: Record<string, string>) => void;
}

/**
 * Show a server error: field errors go onto the form (paths like
 * `items.0.width` match Mantine form paths), anything else becomes a toast.
 */
export function handleFormError(error: unknown, form?: FormLike, title = 'Could not save'): void {
  if (error instanceof ApiError && form && Object.keys(error.fieldErrors).length > 0) {
    form.setErrors(error.fieldErrors);
    const general = error.items.find((i) => !i.attr || i.attr === 'non_field_errors');
    if (!general) {
      notifications.show({
        color: 'red',
        title,
        message: 'Please correct the highlighted fields.',
      });
      return;
    }
  }
  notifications.show({ color: 'red', title, message: errorMessage(error) });
}

export function notifySuccess(message: string, title?: string): void {
  notifications.show({ color: 'green', title, message });
}

export function notifyError(error: unknown, title = 'Something went wrong'): void {
  notifications.show({ color: 'red', title, message: errorMessage(error) });
}

/** Convert '' to null for optional numeric/date fields before sending. */
export function blankToNull<T extends Record<string, unknown>>(values: T): T {
  return Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v === '' ? null : v])) as T;
}
