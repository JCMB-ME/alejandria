<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { auth } from '$api/client';
  import { setUser } from '$stores/auth';
  import Logo from '$components/Logo.svelte';
  import toast from '$components/Toaster.svelte';
  import { t } from '$stores/i18n';

  let username = $state('');
  let password = $state('');
  let loading = $state(false);
  let error = $state('');

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    error = '';
    loading = true;
    try {
      const res = await auth.login(username, password);
      setUser(res.user);
      const next = $page.url.searchParams.get('next') || '/';
      goto(next, { replaceState: true });
    } catch (e: any) {
      error = e.detail || $t('login_failed');
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>{$t('sign_in')} — Alejandría</title>
</svelte:head>

<div class="w-full max-w-md">
  <div class="flex justify-center mb-8">
    <Logo size={64} />
  </div>
  <div class="card p-8">
    <h1 class="font-serif text-2xl mb-6 text-center">{$t('sign_in')}</h1>
    <form onsubmit={handleSubmit} class="space-y-4">
      <div>
        <label for="username" class="block text-sm font-medium mb-1.5">{$t('username')}</label>
        <input
          id="username"
          type="text"
          bind:value={username}
          required
          autocomplete="username"
          class="input"
          placeholder="admin"
        />
      </div>
      <div>
        <label for="password" class="block text-sm font-medium mb-1.5">{$t('password')}</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          required
          autocomplete="current-password"
          class="input"
        />
      </div>
      {#if error}
        <div class="text-sm text-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] px-3 py-2 rounded">
          {error}
        </div>
      {/if}
      <button type="submit" class="btn btn-primary w-full" disabled={loading}>
        {loading ? $t('signing_in') : $t('sign_in')}
      </button>
    </form>
  </div>
</div>
