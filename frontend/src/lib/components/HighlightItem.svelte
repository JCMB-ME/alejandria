<script lang="ts">
  /**
   * One row in the reader highlights drawer (Plan 3 / H4 + H5).
   * Encapsulates the per-row note input, color picker, and delete button
   * so the parent drawer's state stays simple. Saves the note on blur
   * (not on keystroke) to avoid spamming PATCHes.
   */
  import type { Highlight } from '$api/types';
  import { highlights as highlightsApi } from '$api/client';
  import { t } from '$stores/i18n';
  import { toast } from '$stores/toast';
  import HighlightColorPicker from './HighlightColorPicker.svelte';

  interface Props {
    highlight: Highlight;
    bookFormatType: 'epub' | 'pdf' | 'cbz' | 'fb2' | 'rtf' | 'txt' | null;
    onJump: (h: Highlight) => void;
    onDelete: (id: number) => void;
  }
  let { highlight: h, bookFormatType, onJump, onDelete }: Props = $props();

  // Local copy so typing doesn't trigger a parent re-render. We compare
  // against the stored value on blur to skip no-op PATCHes.
  let note = $state(h.note ?? '');
  let saving = $state(false);

  async function saveNote() {
    if (note === (h.note ?? '')) return;
    saving = true;
    try {
      const updated = await highlightsApi.update(h.id, { note: note || null });
      h = updated;
    } catch {
      toast.error('Could not save note');
    } finally {
      saving = false;
    }
  }

  async function setColor(color: string) {
    if (color === h.color) return;
    try {
      h = await highlightsApi.update(h.id, { color });
    } catch {
      toast.error('Could not change color');
    }
  }
</script>

<div class="flex items-start gap-2">
  <button
    type="button"
    class="flex-1 min-w-0 text-left rounded p-2 hover:bg-[var(--elevated)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
    aria-label={`Jump to highlight: ${h.text.slice(0, 40)}`}
    onclick={() => onJump(h)}
  >
    <div class="flex items-baseline gap-2">
      <blockquote
        class="border-l-2 pl-2 italic flex-1 min-w-0"
        style="border-color: {h.color};"
      >
        {h.text}
      </blockquote>
      {#if (bookFormatType === 'pdf' || bookFormatType === 'cbz') && h.page != null}
        <span class="text-[10px] text-[var(--text-muted)] whitespace-nowrap shrink-0">
          {$t('highlight_on_page', { n: h.page })}
        </span>
      {/if}
    </div>
    <textarea
      class="input mt-2 w-full text-sm"
      rows="2"
      placeholder={$t('highlight_note_placeholder')}
      bind:value={note}
      onblur={saveNote}
      aria-label={$t('highlight_note_placeholder')}
    ></textarea>
    <HighlightColorPicker current={h.color} onChange={setColor} />
    {#if saving}<span class="text-[10px] text-[var(--text-muted)]">…</span>{/if}
  </button>
  <button
    type="button"
    class="btn btn-ghost !p-1.5 shrink-0 text-[var(--text-soft)] hover:text-[var(--danger)]"
    aria-label={$t('delete_highlight')}
    title={$t('delete_highlight')}
    onclick={(e) => { e.stopPropagation(); onDelete(h.id); }}
  >
    <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/>
      <path d="M10 11v6"/>
      <path d="M14 11v6"/>
      <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>
    </svg>
  </button>
</div>