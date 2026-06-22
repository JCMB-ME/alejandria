/**
 * Toast notification store.
 */
import { writable } from 'svelte/store';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: number;
  message: string;
  type: ToastType;
  duration: number;
}

const toasts = writable<Toast[]>([]);
let nextId = 0;

export const toast = {
  show(message: string, type: ToastType = 'info', duration = 3000) {
    const id = ++nextId;
    toasts.update((arr) => [...arr, { id, message, type, duration }]);
    if (duration > 0) {
      setTimeout(() => toast.dismiss(id), duration);
    }
  },
  success(m: string, d?: number) {
    this.show(m, 'success', d);
  },
  error(m: string, d?: number) {
    this.show(m, 'error', d);
  },
  info(m: string, d?: number) {
    this.show(m, 'info', d);
  },
  warning(m: string, d?: number) {
    this.show(m, 'warning', d);
  },
  dismiss(id: number) {
    toasts.update((arr) => arr.filter((t) => t.id !== id));
  },
};

export { toasts };
