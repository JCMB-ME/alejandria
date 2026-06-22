<script lang="ts">
  import { page } from '$app/stores';
  import Logo from './Logo.svelte';
  import { user } from '$stores/auth';

  import { t } from '$stores/i18n';

  // Bound from layout. When true, the drawer is open (mobile only — desktop
  // ignores this and always shows the sidebar).
  let { mobileOpen = $bindable(false) }: { mobileOpen?: boolean } = $props();

  const items = [
    { href: '/', key: 'home', icon: 'home' },
    { href: '/library', key: 'library', icon: 'library' },
    { href: '/shelves', key: 'shelves', icon: 'shelves' },
    { href: '/stats', key: 'stats', icon: 'stats' },
    { href: '/settings', key: 'settings', icon: 'settings' },
  ] as const;

  function isActive(href: string) {
    if (href === '/') return $page.url.pathname === '/';
    return $page.url.pathname.startsWith(href);
  }

  function close() {
    mobileOpen = false;
  }
</script>

<!-- Backdrop (mobile only) -->
{#if mobileOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 bg-black/50 z-40 md:hidden"
    onclick={close}
    role="presentation"
  ></div>
{/if}

<!-- Sidebar: drawer on mobile, static column on desktop -->
<aside
  class="fixed md:static inset-y-0 left-0 z-50 w-72 md:w-60 md:shrink-0 border-r flex flex-col transition-transform duration-200 ease-out md:translate-x-0"
  class:translate-x-0={mobileOpen}
  class:-translate-x-full={!mobileOpen}
  style="background: var(--surface); border-color: var(--border);"
  aria-label="Main navigation"
>
  <div class="h-16 flex items-center justify-between px-5 border-b shrink-0" style="border-color: var(--border);">
    <Logo size={32} showText />
    <!-- Close (mobile only) -->
    <button
      class="btn btn-ghost !p-1.5 md:hidden"
      onclick={close}
      aria-label="Close menu"
    >
      <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    </button>
  </div>

  <nav class="flex-1 p-3 space-y-0.5 overflow-y-auto">
    {#each items as item}
      <a
        href={item.href}
        onclick={close}
        class="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors"
        class:active={isActive(item.href)}
        style:background={isActive(item.href) ? 'var(--accent)' : 'transparent'}
        style:color={isActive(item.href) ? 'var(--accent-text)' : 'var(--text-muted)'}
      >
        {#if item.icon === 'home'}
          <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        {:else if item.icon === 'library'}
          <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
        {:else if item.icon === 'shelves'}
          <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        {:else if item.icon === 'stats'}
          <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>
        {:else}
          <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        {/if}
        {$t(item.key)}
      </a>
    {/each}
  </nav>

  {#if $user}
    <div class="p-3 border-t shrink-0" style="border-color: var(--border);">
      <div class="flex items-center gap-2.5 px-2 py-2">
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold shrink-0" style="background: var(--accent); color: var(--accent-text);">
          {($user.display_name || $user.username).charAt(0).toUpperCase()}
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium truncate">{$user.display_name || $user.username}</div>
          <div class="text-xs text-[var(--text-soft)] truncate">{$user.role}</div>
        </div>
      </div>
    </div>
  {/if}
</aside>

<style>
  .active:hover {
    filter: brightness(1.1);
  }
</style>
