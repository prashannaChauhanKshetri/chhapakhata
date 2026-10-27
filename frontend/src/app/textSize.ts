/**
 * Text size (accessibility). Every size in the app is in rem, so changing the
 * root font size scales text, buttons and spacing together. The choice is
 * remembered on this device only; the browser's own font-size setting still
 * applies on top.
 */
import { useSyncExternalStore } from 'react';

export const TEXT_SIZES = [
  { value: 'normal', label: 'Normal', percent: 100 },
  { value: 'large', label: 'Large', percent: 112.5 },
  { value: 'larger', label: 'Extra large', percent: 125 },
] as const;

export type TextSize = (typeof TEXT_SIZES)[number]['value'];

const KEY = 'ck-text-size';
const listeners = new Set<() => void>();

function read(): TextSize {
  try {
    const saved = localStorage.getItem(KEY);
    return TEXT_SIZES.some((s) => s.value === saved) ? (saved as TextSize) : 'normal';
  } catch {
    return 'normal';
  }
}

let current: TextSize = typeof window === 'undefined' ? 'normal' : read();

function apply(size: TextSize) {
  const percent = TEXT_SIZES.find((s) => s.value === size)?.percent ?? 100;
  document.documentElement.style.fontSize = percent === 100 ? '' : `${percent}%`;
}

/** Call once at start-up, before the first render. */
export function applySavedTextSize(): void {
  apply(current);
}

export function setTextSize(size: TextSize): void {
  current = size;
  apply(size);
  try {
    localStorage.setItem(KEY, size);
  } catch {
    // Storage blocked: the size still applies until the page is reloaded.
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useTextSize(): TextSize {
  return useSyncExternalStore(subscribe, () => current);
}
