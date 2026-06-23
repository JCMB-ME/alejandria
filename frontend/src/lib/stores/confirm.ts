import { writable, derived } from 'svelte/store';

/**
 * Promise-based confirmation service — drop-in replacement for window.confirm().
 *
 * Usage:
 *   if (!await confirm({ title, message, danger: true })) return;
 *
 * Edge case: if two `confirm()` calls happen in quick succession, the first
 * Promise resolves with `false` (no action taken) and the second dialog wins.
 * This matches the project convention of rejecting destructive actions on
 * ambiguity.
 */

export interface ConfirmRequest {
  title: string;
  message: string | string[];   // array → render each on its own paragraph
  confirmLabel?: string;        // defaults to $t('delete_btn') at call-site
  cancelLabel?: string;         // defaults to $t('cancel_btn')
  danger?: boolean;             // default true
}

interface ConfirmState {
  request: ConfirmRequest | null;
  resolver: ((ok: boolean) => void) | null;
}

const state = writable<ConfirmState>({ request: null, resolver: null });

// Expose the active request (or null) for the host to render. The resolver
// stays internal to this module — callers resolve via resolveConfirm().
export const confirmRequest = derived(state, ($s) => $s.request);

export function confirm(req: ConfirmRequest): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    // Replace strategy: if a confirm is already open, the new one wins.
    // The previous Promise resolves with `false` (effectively cancelled by the UI).
    state.update((s) => {
      if (s.resolver) s.resolver(false);
      return { request: req, resolver: resolve };
    });
  });
}

export function resolveConfirm(ok: boolean) {
  state.update((s) => {
    if (s.resolver) s.resolver(ok);
    return { request: null, resolver: null };
  });
}