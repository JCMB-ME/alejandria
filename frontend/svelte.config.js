import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build/client',
      assets: 'build/client',
      fallback: 'index.html', // SPA fallback
      precompress: false,
      strict: false,
      envPrefix: 'PUBLIC_',
    }),
    csrf: {
      checkOrigin: true,
    },
    alias: {
      $components: 'src/lib/components',
      $stores: 'src/lib/stores',
      $api: 'src/lib/api',
      $reader: 'src/lib/reader',
    },
  },
};

export default config;
