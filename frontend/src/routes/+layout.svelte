<script lang="ts">
  import '../app.css';
  import { onMount, untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { user, initTheme, loadUser } from '$stores/auth';
  import Sidebar from '$components/Sidebar.svelte';
  import Header from '$components/Header.svelte';
  import Toaster from '$components/Toaster.svelte';
  import ScraperNotifier from '$components/ScraperNotifier.svelte';
  import ConfirmDialog from '$components/ConfirmDialog.svelte';
  import SecurityBanner from '$components/SecurityBanner.svelte';

  import { initLanguage } from '$stores/i18n';
  import { confirmRequest, resolveConfirm } from '$stores/confirm';
  import { auth as authApi } from '$api/client';

  let { children } = $props();

  // Mobile drawer state — shared between Header (hamburger) and Sidebar (drawer).
  let mobileMenuOpen = $state(false);

  // null = still probing, true = first-time setup (no users), false = users exist
  let needsSetup = $state<boolean | null>(null);

  // Close the drawer whenever the route changes.
  $effect(() => {
    void $page.url.pathname;
    untrack(() => {
      mobileMenuOpen = false;
    });
  });

  onMount(async () => {
    initTheme();
    initLanguage();
    await loadUser();

    // Probe first-time setup status once per load.
    try {
      const status = await authApi.setupStatus();
      needsSetup = status.needs_setup;
    } catch {
      // If the probe fails, don't block — just behave as if setup is done.
      needsSetup = false;
    }

    const path = $page.url.pathname;
    const isLogin = path.startsWith('/login');
    const isRegister = path.startsWith('/register');

    // If logged in, send to home from any auth page.
    if ($user && (isLogin || isRegister)) {
      goto('/');
      return;
    }

    // If NOT logged in:
    if (!$user) {
      if (needsSetup && !isRegister) {
        // First-time setup → /register
        goto('/register');
      } else if (!needsSetup && isRegister) {
        // Users exist → don't show register, go to login
        goto('/login');
      } else if (!needsSetup && !isLogin && !isRegister) {
        // Any other authed-only page → /login
        goto('/login?next=' + encodeURIComponent(path + $page.url.search));
      }
    }
  });
</script>

<Toaster />
<ScraperNotifier />
<SecurityBanner />
<ConfirmDialog request={$confirmRequest} onResolve={resolveConfirm} />

{#if $user}
  {#if $page.url.pathname.startsWith('/read/')}
    {@render children()}
  {:else}
    <div class="flex h-screen overflow-hidden">
      <Sidebar bind:mobileOpen={mobileMenuOpen} />
      <div class="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header bind:mobileMenuOpen />
        <main class="flex-1 overflow-y-auto">
          {@render children()}
        </main>
      </div>
    </div>
  {/if}
{:else}
  <div class="min-h-screen flex items-center justify-center px-4 py-8">
    {@render children()}
  </div>
{/if}
