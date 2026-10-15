import { Button, Center, Stack, Text, Title } from '@mantine/core';
import { Component, type ErrorInfo, type ReactNode } from 'react';

interface State {
  error: Error | null;
}

/** Catches crashes outside page routes (dialogs, providers) so the screen never goes blank. */
export class AppErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Unhandled UI error', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <Center mih="100vh" p="lg">
        <Stack align="center" gap="sm" maw={460} ta="center">
          <Title order={2}>Something went wrong on this screen</Title>
          <Text c="dimmed">
            Your saved data is safe. Reload to continue; if it happens again, tell the owner what
            you were doing.
          </Text>
          <Text size="xs" c="dimmed" ff="monospace">
            {this.state.error.message}
          </Text>
          <Button mt="sm" onClick={() => window.location.reload()}>
            Reload
          </Button>
        </Stack>
      </Center>
    );
  }
}
