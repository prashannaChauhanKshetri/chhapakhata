import { Button } from '@mantine/core';
import { IconMapPinOff } from '@tabler/icons-react';
import { Link } from 'react-router';

import { EmptyState } from '@/components/EmptyState';

export default function NotFoundPage() {
  return (
    <EmptyState
      icon={<IconMapPinOff size={22} />}
      title="Page not found"
      description="The address may be mistyped, or the record was removed."
      action={
        <Button component={Link} to="/" variant="default">
          Go to dashboard
        </Button>
      }
    />
  );
}
