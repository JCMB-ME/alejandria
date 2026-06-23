<script lang="ts">
  import { t } from '$stores/i18n';

  interface Props {
    mode: 'add' | 'remove' | 'set';
    onClose: () => void;
    onApply: (tags: string[]) => void;
  }
  let { mode, onClose, onApply }: Props = $props();

  let input = $state('');
  let tags = $state<string[]>([]);

  function commitInput() {
    const parts = input
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    for (const p of parts) {
      if (!tags.includes(p)) tags.push(p);
    }
    input = '';
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      commitInput();
    } else if (e.key === 'Backspace' && input === '' && tags.length > 0) {
      tags = tags.slice(0, -1);
    }
  }

  function removeTag(t: string) {
    tags = tags.filter((x) => x !== t);
  }

  function apply() {
    if (input.trim()) commitInput();
    if (tags.length === 0) return;
    onApply(tags);
  }

  function handleKeydownGlobal(e: KeyboardEvent) {
    if (e.key === 'Escape') onClose();
  }

  const titleKey = $derived(
    mode === 'add'
      ? 'bulk_choose_tags'
      : mode === 'remove'
        ? 'bulk_choose_tags_remove'
        : 'bulk_choose_tags_set',
  );
</script>

<svelte:window onkeydown={handleKeydownGlobal} />

<div
  class="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
  role="dialog"
  aria-modal="true"
  aria-labelledby="tag-input-title"
  tabindex="-1"
  onclick={(e) => { if (e.target === e.currentTarget) onClose(); }}
  onkeydown={handleKeydownGlobal}
>
  <div
    class="w-full max-w-md rounded-xl shadow-2xl border overflow-hidden"
    style="background: var(--surface); border-color: var(--border);"
  >
    <div class="px-6 py-4 flex items-center justify-between border-b" style="border-color: var(--border);">
      <h2 id="tag-input-title" class="text-lg font-semibold">{$t(titleKey)}</h2>
      <button
        type="button"
        class="w-8 h-8 inline-flex items-center justify-center rounded-full hover:bg-[var(--surface-hover)]"
        aria-label="Close"
        onclick={onClose}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/>
        </svg>
      </button>
    </div>

    <div class="px-6 py-4 space-y-3">
      <input
        type="text"
        class="input w-full"
        bind:value={input}
        onkeydown={onKeydown}
        placeholder={$t(titleKey)}
      />
      {#if tags.length > 0}
        <div class="flex flex-wrap gap-1.5">
          {#each tags as tag (tag)}
            <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border" style="background: var(--surface-hover); border-color: var(--border);">
              {tag}
              <button
                type="button"
                class="hover:text-[var(--danger)]"
                aria-label={`Remove ${tag}`}
                onclick={() => removeTag(tag)}
              >×</button>
            </span>
          {/each}
        </div>
      {/if}
    </div>

    <div class="px-6 py-3 border-t flex justify-end gap-2" style="border-color: var(--border);">
      <button type="button" class="btn btn-ghost" onclick={onClose}>
        {$t('bulk_cancel')}
      </button>
      <button type="button" class="btn btn-primary" onclick={apply} disabled={tags.length === 0 && !input.trim()}>
        {$t('bulk_apply')}
      </button>
    </div>
  </div>
</div>
