<script lang="ts">
  import { goto } from '$app/navigation';
  import { auth } from '$api/client';
  import { setUser } from '$stores/auth';
  import Logo from '$components/Logo.svelte';
  import toast from '$components/Toaster.svelte';
  import { t } from '$stores/i18n';

  let username = $state('');
  let displayName = $state('');
  let email = $state('');
  let password = $state('');
  let passwordConfirm = $state('');
  let loading = $state(false);
  let error = $state('');

  function validate(): string {
    if (username.length < 3) return 'Username must be at least 3 characters';
    if (!/^[a-zA-Z0-9_.-]+$/.test(username)) return 'Username can only contain letters, numbers, _, ., -';
    if (!email.includes('@')) return 'Please enter a valid email';
    if (password.length < 8) return 'Password must be at least 8 characters';
    if (password !== passwordConfirm) return 'Passwords do not match';
    return '';
  }

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    error = '';
    const v = validate();
    if (v) {
      error = v;
      return;
    }
    loading = true;
    try {
      const res = await auth.register({
        username,
        email,
        password,
        display_name: displayName.trim() || undefined,
      });
      setUser(res.user);
      toast.success($t('account_created'));
      goto('/', { replaceState: true });
    } catch (e: any) {
      error = e?.detail || $t('registration_failed');
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>{$t('create_account')} — Alejandría</title>
</svelte:head>

<div class="w-full max-w-md">
  <div class="flex justify-center mb-6">
    <Logo size={64} />
  </div>
  <div class="card p-6 md:p-8">
    <h1 class="font-serif text-2xl mb-1 text-center">{$t('setup_welcome')}</h1>
    <p class="text-sm text-[var(--text-soft)] text-center mb-6">{$t('setup_subtitle')}</p>
    <div class="mb-5 text-xs px-3 py-2 rounded border border-[var(--border)] bg-[var(--elevated)] text-[var(--text-muted)]">
      {$t('setup_admin_note')}
    </div>
    <form onsubmit={handleSubmit} class="space-y-4">
      <div>
        <label for="username" class="block text-sm font-medium mb-1.5">{$t('username')}</label>
        <input
          id="username"
          type="text"
          bind:value={username}
          required
          autocomplete="username"
          minlength="3"
          class="input"
          placeholder="admin"
        />
      </div>
      <div>
        <label for="display_name" class="block text-sm font-medium mb-1.5">{$t('display_name')}</label>
        <input
          id="display_name"
          type="text"
          bind:value={displayName}
          autocomplete="name"
          class="input"
          placeholder={$t('display_name_placeholder')}
        />
      </div>
      <div>
        <label for="email" class="block text-sm font-medium mb-1.5">{$t('email')}</label>
        <input
          id="email"
          type="email"
          bind:value={email}
          required
          autocomplete="email"
          class="input"
          placeholder={$t('email_placeholder')}
        />
      </div>
      <div>
        <label for="password" class="block text-sm font-medium mb-1.5">{$t('password')}</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          required
          autocomplete="new-password"
          minlength="8"
          class="input"
        />
      </div>
      <div>
        <label for="password_confirm" class="block text-sm font-medium mb-1.5">{$t('password')}</label>
        <input
          id="password_confirm"
          type="password"
          bind:value={passwordConfirm}
          required
          autocomplete="new-password"
          minlength="8"
          class="input"
        />
      </div>
      {#if error}
        <div class="text-sm text-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] px-3 py-2 rounded">
          {error}
        </div>
      {/if}
      <button type="submit" class="btn btn-primary w-full" disabled={loading}>
        {loading ? $t('creating_account') : $t('create_account')}
      </button>
    </form>
  </div>
</div>
