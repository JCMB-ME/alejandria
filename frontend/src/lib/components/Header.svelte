<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { theme, setTheme, readerTheme, setReaderTheme, customThemes } from '$stores/auth';
  import { auth } from '$api/client';
  import { clearUser } from '$stores/auth';
  import { t } from '$stores/i18n';

  let search = $state('');
  let showThemeMenu = $state(false);

  let activeBase = $derived(
    $theme === 'light' || $theme === 'dark' || $theme === 'sepia'
      ? $theme
      : ($customThemes.find(ct => ct.id === $theme)?.base || 'light')
  );

  function handleSearch(e: SubmitEvent) {
    e.preventDefault();
    if (search.trim()) {
      goto(`/library?search=${encodeURIComponent(search.trim())}`);
    }
  }

  async function logout() {
    try {
      await auth.logout();
    } catch {}
    clearUser();
    goto('/login');
  }
</script>

<header class="h-16 border-b flex items-center px-4 md:px-6 gap-3" style="background: var(--surface); border-color: var(--border);">
  <form onsubmit={handleSearch} class="flex-1 max-w-xl">
    <div class="relative">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
      </svg>
      <input
        type="search"
        bind:value={search}
        placeholder={$t('search_library_placeholder')}
        class="input pl-9"
      />
    </div>
  </form>

  <div class="flex items-center gap-1">
    <div class="relative flex items-center justify-center">
      {#if showThemeMenu}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="fixed inset-0 z-40 cursor-default" onclick={() => showThemeMenu = false}></div>
      {/if}

      <button
        class="btn btn-ghost !p-2 z-50 relative"
        onclick={() => showThemeMenu = !showThemeMenu}
        aria-label="Toggle theme"
        title={$t('theme')}
      >
        {#if activeBase === 'light'}
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        {:else if activeBase === 'dark'}
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        {:else}
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
        {/if}
      </button>

      {#if showThemeMenu}
        <div class="absolute right-0 top-full mt-1.5 w-48 rounded-md shadow-lg py-1 border z-50 bg-[var(--surface)] border-[var(--border)] overflow-hidden">
          <!-- System themes -->
          {#each ['light', 'sepia', 'dark'] as tVal}
            <button
              class="w-full text-left px-4 py-2.5 text-sm flex items-center justify-between hover:bg-[var(--elevated)] transition-colors text-[var(--text)]"
              class:font-medium={$theme === tVal}
              onclick={() => { setTheme(tVal); showThemeMenu = false; }}
            >
              <span class="capitalize">{tVal}</span>
              {#if $theme === tVal}
                <svg class="w-4 h-4 text-[var(--accent)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              {/if}
            </button>
          {/each}

          {#if $customThemes.length > 0}
            <div class="border-t border-[var(--border)] my-1"></div>
            <!-- Custom themes -->
            {#each $customThemes as ct}
              <button
                class="w-full text-left px-4 py-2.5 text-sm flex items-center justify-between hover:bg-[var(--elevated)] transition-colors text-[var(--text)]"
                class:font-medium={$theme === ct.id}
                onclick={() => { setTheme(ct.id); showThemeMenu = false; }}
              >
                <div class="flex items-center gap-2 min-w-0">
                  <span class="w-3 h-3 rounded-full border border-[var(--border)] shrink-0" style:background={ct.colors.accent}></span>
                  <span class="truncate">{ct.name}</span>
                </div>
                {#if $theme === ct.id}
                  <svg class="w-4 h-4 text-[var(--accent)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                {/if}
              </button>
            {/each}
          {/if}
        </div>
      {/if}
    </div>

    <a href="/opds" target="_blank" class="btn btn-ghost !p-2" title={$t('opds_feed')}>
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>
    </a>

    <button class="btn btn-ghost !p-2" onclick={logout} title={$t('logout')}>
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
    </button>
  </div>
</header>
