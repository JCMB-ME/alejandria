/**
 * Disable SSR for now (SvelteKit is mostly client-side here).
 * We rely on the FastAPI backend for all data.
 */
export const ssr = false;
export const prerender = false;
