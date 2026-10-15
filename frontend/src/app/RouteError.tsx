import { Button, Center, Code, Stack, Text, Title } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import { isRouteErrorResponse, Link, useRouteError } from 'react-router';

/** Last-resort screen if a page crashes. Keeps the rest of the app usable. */
export function RouteError() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  return (
    <Center mih="70vh" p="lg">
      <Stack align="center" gap="sm" maw={480} ta="center">
        <IconAlertTriangle size={40} stroke={1.5} color="var(--mantine-color-amber-7)" />
        <Title order={2}>{notFound ? 'Page not found' : 'This page ran into a problem'}</Title>
        <Text c="dimmed">
          {notFound
            ? 'The address may be mistyped, or the record was removed.'
            : 'Your data is safe. Reload the page; if it happens again, tell the owner what you were doing.'}
        </Text>
        {!notFound && error instanceof Error && (
          <Code block maw="100%" style={{ textAlign: 'left' }}>
            {error.message}
          </Code>
        )}
        <Button.Group mt="sm">
          <Button variant="default" onClick={() => window.location.reload()}>
            Reload
          </Button>
          <Button component={Link} to="/">
            Dashboard
          </Button>
        </Button.Group>
      </Stack>
    </Center>
  );
}
