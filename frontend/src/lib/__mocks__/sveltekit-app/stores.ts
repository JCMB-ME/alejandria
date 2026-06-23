// Vitest stub: $app/stores
import { writable, type Readable } from 'svelte/store';

export const page: Readable<{
  url: URL;
  params: Record<string, string>;
  route: { id: string | null };
  status: number;
  error: Error | null;
  data: Record<string, unknown>;
}> = writable({
  url: new URL('http://localhost/'),
  params: {},
  route: { id: null },
  status: 200,
  error: null,
  data: {},
});

export const navigating: Readable<null | { to: { url: URL; route: { id: string | null }; params: Record<string, string> } }> = writable(null);

export const updated = writable(false);
