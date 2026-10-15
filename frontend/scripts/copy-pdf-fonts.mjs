// Copies the WOFF font files that the backend's PDF templates use into
// backend/fonts, so invoices render with the same typeface offline.
// Fonts: Inter and Noto Sans Devanagari, both SIL Open Font License 1.1.
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const target = join(here, '..', '..', 'backend', 'fonts');
mkdirSync(target, { recursive: true });

const files = [
  ['@fontsource/inter', 'inter-latin-400-normal.woff'],
  ['@fontsource/inter', 'inter-latin-500-normal.woff'],
  ['@fontsource/inter', 'inter-latin-600-normal.woff'],
  ['@fontsource/inter', 'inter-latin-700-normal.woff'],
  ['@fontsource/noto-sans-devanagari', 'noto-sans-devanagari-devanagari-400-normal.woff'],
  ['@fontsource/noto-sans-devanagari', 'noto-sans-devanagari-devanagari-600-normal.woff'],
];

for (const [pkg, file] of files) {
  copyFileSync(join(here, '..', 'node_modules', pkg, 'files', file), join(target, file));
  console.log(`copied ${file}`);
}
