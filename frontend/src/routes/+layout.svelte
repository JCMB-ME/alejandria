<script lang="ts">
  import '../app.css';
  import { onMount, untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { user, initTheme, loadUser } from '$stores/auth';
  import Sidebar from '$components/Sidebar.svelte';
  import Header from '$components/Header.svelte';
  import Toaster from '$components/Toaster.svelte';

  import { initLanguage } from '$stores/i18n';

  let { children } = $props();

  // Mobile drawer state — shared between Header (hamburger) and Sidebar (drawer).
  let mobileMenuOpen = $state(false);

  // Close the drawer whenever the route changes.
  $effect(() => {
    // Touch $page.url.pathname so this re-runs on navigation
    void $page.url.pathname;
    untrack(() => {
      mobileMenuOpen = false;
    });
  });

  onMount(async () => {
    initTheme();
    initLanguage();
    await loadUser();
    // Redirect to login if not authenticated and not already on login page
    const isPublic = $page.url.pathname.startsWith('/login');
    if (!$user && !isPublic) {
      goto('/login?next=' + encodeURIComponent($page.url.pathname + $page.url.search));
    }
    // Defensive: if already logged in but on /login, send home
    if ($user && isPublic) {
      goto('/');
    }
  });
</script>

<Toaster />

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
