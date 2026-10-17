/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

const backend = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';

// HTTPS for the dev server on the local network (`make lan-frontend`), with a
// certificate made by `make lan-cert`. Phones only allow installing the app and
// working offline over HTTPS.
const certDir = fileURLToPath(new URL('../.certs/', import.meta.url));
const https =
  process.env.VITE_HTTPS === '1' && existsSync(`${certDir}dev.pem`)
    ? { cert: readFileSync(`${certDir}dev.pem`), key: readFileSync(`${certDir}dev-key.pem`) }
    : undefined;

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // A new version waits until the user chooses to reload (see UpdatePrompt).
      registerType: 'prompt',
      injectRegister: false,
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon-180.png'],
      manifest: {
        id: '/',
        name: 'ChhapaKhata · OM Traders',
        short_name: 'ChhapaKhata',
        description: 'Orders, production, stock and billing for OM Traders and Suppliers.',
        lang: 'en',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'any',
        background_color: '#F8FAFC',
        theme_color: '#0F172A',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          {
            src: '/icons/icon-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
        shortcuts: [
          { name: 'New order', url: '/orders/new' },
          { name: 'Production board', url: '/production' },
        ],
      },
      workbox: {
        // The app itself (pages, scripts, fonts) is stored on the device so it
        // opens without the server. Business data is never cached here; the app
        // keeps its own copy of what was last seen (see app/offline.ts).
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/django-admin/, /^\/media\//, /^\/static\//],
        cleanupOutdatedCaches: true,
      },
      devOptions: { enabled: process.env.VITE_PWA_DEV === '1', type: 'module' },
    }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    https,
    // Same-origin in development too: the session cookie and CSRF work unchanged.
    proxy: {
      '/api': { target: backend, changeOrigin: false },
      '/media': { target: backend, changeOrigin: false },
      '/django-admin': { target: backend, changeOrigin: false },
      '/static': { target: backend, changeOrigin: false },
    },
  },
  build: {
    sourcemap: true,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router'],
          mantine: [
            '@mantine/core',
            '@mantine/hooks',
            '@mantine/dates',
            '@mantine/form',
            '@mantine/modals',
            '@mantine/notifications',
          ],
          charts: ['@mantine/charts', 'recharts'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
