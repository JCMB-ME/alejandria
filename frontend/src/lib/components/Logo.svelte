<script lang="ts">
  /**
   * Logo component — the Greek/Roman column with architrave.
   * Optimized inline SVG that adapts to theme.
   */
  interface Props {
    size?: number;
    showText?: boolean;
  }
  let { size = 32, showText = false }: Props = $props();
</script>

<a href="/" class="flex items-center gap-2.5 group !text-[var(--text)] hover:no-underline" aria-label="Alejandría home">
  <svg
    width={size}
    height={size}
    viewBox="0 0 100 100"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="transition-transform group-hover:scale-105"
  >
    <!-- Architrave (top slab) -->
    <path
      d="M 8 22 L 92 22 L 88 32 L 12 32 Z"
      fill="currentColor"
    />
    <!-- Architrave bottom band -->
    <rect x="14" y="33" width="72" height="3" fill="currentColor" opacity="0.6" />
    <!-- Capital scroll ends (left volute) -->
    <path
      d="M 14 36 C 8 36 6 42 10 46 C 12 48 16 48 18 46 C 20 44 20 40 17 39"
      stroke="currentColor"
      stroke-width="2.2"
      stroke-linecap="round"
      fill="none"
    />
    <path
      d="M 86 36 C 92 36 94 42 90 46 C 88 48 84 48 82 46 C 80 44 80 40 83 39"
      stroke="currentColor"
      stroke-width="2.2"
      stroke-linecap="round"
      fill="none"
    />
    <!-- Capital top -->
    <path
      d="M 14 36 L 86 36 L 84 42 L 16 42 Z"
      fill="currentColor"
    />
    <!-- Column flutes (5 vertical lines) -->
    {#each [28, 38, 48, 58, 68] as x}
      <line
        x1={x}
        y1="46"
        x2={x}
        y2="92"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
      />
    {/each}
  </svg>
  {#if showText}
    <span class="font-serif text-xl tracking-tight">Alejandría</span>
  {/if}
</a>
