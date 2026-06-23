<script lang="ts">
  interface Props {
    label: string;
    value: string;
    onRemove: () => void;
  }
  let { label, value, onRemove }: Props = $props();
</script>

<span
  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border"
  style="background: color-mix(in srgb, var(--accent) 10%, transparent); border-color: color-mix(in srgb, var(--accent) 30%, var(--border)); color: var(--text);"
>
  <span class="text-[var(--text-muted)]">{label}:</span>
  <span class="font-medium">{value}</span>
  <button
    type="button"
    class="ml-1 -mr-1 inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
    aria-label={`Remove filter ${label} ${value}`}
    onclick={onRemove}
  >
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
      <line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/>
    </svg>
  </button>
</span>
