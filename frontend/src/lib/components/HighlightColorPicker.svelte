<script lang="ts">
  /**
   * 5-swatch color picker for highlight rows in the reader drawer.
   * Hex values mirror the Alembic migration's CASE branches so what
   * you see is exactly what gets stored and re-rendered by app.css.
   */
  import { t } from '$stores/i18n';

  interface Props {
    current: string;
    onChange: (color: string) => void;
  }
  let { current, onChange }: Props = $props();

  const swatches = [
    { hex: '#FFEB3B', name: 'yellow' },
    { hex: '#81C784', name: 'green' },
    { hex: '#64B5F6', name: 'blue' },
    { hex: '#F48FB1', name: 'pink' },
    { hex: '#B39DDB', name: 'purple' },
  ];
</script>

<div class="flex items-center gap-1 mt-1" role="radiogroup" aria-label="Highlight color">
  <span class="text-[10px] text-[var(--text-muted)] mr-1">{$t('highlight_color_label')}</span>
  {#each swatches as s}
    <button
      type="button"
      class="w-5 h-5 rounded-full border focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
      class:ring-2={current === s.hex}
      class:ring-[var(--accent)]={current === s.hex}
      style="background: {s.hex}; border-color: var(--border);"
      role="radio"
      aria-checked={current === s.hex}
      aria-label={s.name}
      title={s.name}
      onclick={() => onChange(s.hex)}
    ></button>
  {/each}
</div>