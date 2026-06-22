import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import path from 'node:path';

export default defineConfig({
  plugins: [svelte({ hot: !process.env.VITEST })],
  resolve: {
    alias: {
      $components: path.resolve(__dirname, 'src/lib/components'),
      $stores: path.resolve(__dirname, 'src/lib/stores'),
      $api: path.resolve(__dirname, 'src/lib/api'),
      $reader: path.resolve(__dirname, 'src/lib/reader'),
    },
  },
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    environment: 'jsdom',
    globals: true,
  },
});
