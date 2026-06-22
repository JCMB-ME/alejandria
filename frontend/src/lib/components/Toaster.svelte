<script lang="ts">
  import { toasts, type ToastType } from '$lib/stores/toast';

  const typeClasses: Record<ToastType, string> = {
    success: 'border-l-success',
    error: 'border-l-error',
    info: 'border-l-info',
    warning: 'border-l-warning',
  };

  const typeColors: Record<ToastType, string> = {
    success: 'var(--success)',
    error: 'var(--danger)',
    info: 'var(--link)',
    warning: 'var(--warning)',
  };
</script>

<div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
  {#each $toasts as t (t.id)}
    <div
      class="pointer-events-auto card px-4 py-3 shadow-elevated animate-slide-up text-sm min-w-[200px] max-w-sm flex items-start gap-2 border-l-4 {typeClasses[t.type]}"
      role="status"
    >
      <div class="w-5 h-5 mt-0.5 shrink-0 flex items-center justify-center" style:color={typeColors[t.type]}>
        {#if t.type === 'success'}
          <svg class="w-full h-full" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        {:else if t.type === 'error'}
          <svg class="w-full h-full" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        {:else if t.type === 'warning'}
          <svg class="w-full h-full" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        {:else}
          <svg class="w-full h-full" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        {/if}
      </div>
      <span class="flex-1">{t.message}</span>
      <button
        class="text-muted hover:text-text leading-none flex items-center justify-center"
        aria-label="Cerrar"
        onclick={() => toasts.update((arr) => arr.filter((x) => x.id !== t.id))}
      >
        <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  {/each}
</div>
