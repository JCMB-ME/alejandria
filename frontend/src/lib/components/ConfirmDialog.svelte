<script lang="ts">
  import type { ConfirmRequest } from '$stores/confirm';
  import { t } from '$stores/i18n';

  let {
    request,
    onResolve
  }: {
    request: ConfirmRequest | null;
    onResolve: (ok: boolean) => void;
  } = $props();

  let cancelBtn: HTMLButtonElement | null = $state(null);
  let confirmBtn: HTMLButtonElement | null = $state(null);

  // Open lifecycle: body scroll lock + default focus.
  // Cleanup runs on unmount AND when `request` flips back to null, so
  // document.body.style.overflow is always restored.
  $effect(() => {
    if (!request) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    // Focus management — default focus on Cancel for safety;
    // on Confirm only when not danger.
    const target = request.danger === false ? confirmBtn : cancelBtn;
    target?.focus();
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      onResolve(false);
      return;
    }
    if (e.key === 'Enter' && !(e.target instanceof HTMLTextAreaElement)) {
      e.preventDefault();
      onResolve(true);
      return;
    }
    if (e.key === 'Tab') {
      // Minimal focus trap between the two buttons.
      const focusables = [cancelBtn, confirmBtn].filter(Boolean) as HTMLElement[];
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }
</script>

{#if request}
  {@const r = request}
  <div
    class="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
    role="alertdialog"
    aria-modal="true"
    aria-labelledby="confirm-title"
    aria-describedby="confirm-body"
    tabindex="-1"
    onclick={(e) => { if (e.target === e.currentTarget) onResolve(false); }}
    onkeydown={handleKeydown}
  >
    <div
      class="w-full max-w-md rounded-xl shadow-2xl border overflow-hidden"
      style="background: var(--surface); border-color: var(--border);"
    >
      <!-- Header band -->
      <div
        class="px-6 py-4 flex items-center gap-3"
        style={r.danger !== false
          ? 'background: color-mix(in srgb, var(--danger) 10%, transparent);'
          : 'background: color-mix(in srgb, var(--accent) 10%, transparent);'}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
             style={r.danger !== false ? 'color: var(--danger);' : 'color: var(--accent);'}
             aria-hidden="true">
          {#if r.danger !== false}
            <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          {:else}
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
          {/if}
        </svg>
        <h2 id="confirm-title" class="text-lg font-semibold text-[var(--text)]">{r.title}</h2>
      </div>

      <!-- Body -->
      <div id="confirm-body" class="px-6 py-4 text-sm text-[var(--text-soft)] space-y-2">
        {#if Array.isArray(r.message)}
          {#each r.message as line}
            <p>{line}</p>
          {/each}
        {:else}
          <p>{r.message}</p>
        {/if}
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t flex justify-end gap-2" style="border-color: var(--border);">
        <button type="button" class="btn btn-ghost" onclick={() => onResolve(false)} bind:this={cancelBtn}>
          {r.cancelLabel ?? $t('cancel_btn')}
        </button>
        <button type="button" class={r.danger !== false ? 'btn btn-danger' : 'btn btn-primary'} onclick={() => onResolve(true)} bind:this={confirmBtn}>
          {r.confirmLabel ?? $t('delete_btn')}
        </button>
      </div>
    </div>
  </div>
{/if}