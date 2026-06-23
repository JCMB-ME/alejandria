<script lang="ts">
  import { onMount } from 'svelte';
  import { auth, users } from '$api/client';
  import { user, setUser, theme, setTheme, readerTheme, setReaderTheme, customThemes, saveCustomTheme, deleteCustomTheme } from '$stores/auth';
  import { t, language, setLanguage } from '$stores/i18n';
  import type { User } from '$api/types';
  import { toast } from '$stores/toast';
  import { confirm } from '$stores/confirm';

  // Custom theme creator state
  let newThemeName = $state('');
  let newThemeBase = $state<'light' | 'dark'>('light');
  let colorBg = $state('#F5F1E8');
  let colorSurface = $state('#FBF7EE');
  let colorBorder = $state('#E4DDD0');
  let colorText = $state('#2A2622');
  let colorAccent = $state('#8B5A2B');

  function handleCreateTheme() {
    if (!newThemeName.trim()) {
      toast.error('Theme name is required');
      return;
    }
    const slug = newThemeName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    const id = `custom-${slug}-${Date.now()}`;
    const newTheme = {
      id,
      name: newThemeName.trim(),
      base: newThemeBase,
      colors: {
        bg: colorBg,
        surface: colorSurface,
        border: colorBorder,
        text: colorText,
        accent: colorAccent,
      }
    };
    saveCustomTheme(newTheme);
    toast.success('Theme created successfully');
    setTheme(id);
    newThemeName = '';
  }

  async function handleDeleteTheme(id: string) {
    if (!await confirm({
      title: $t('delete_theme'),
      message: $t('delete_theme_confirm'),
      confirmLabel: $t('delete_btn'),
      cancelLabel: $t('cancel_btn'),
    })) return;
    deleteCustomTheme(id);
    toast.success('Theme deleted');
  }

  interface MirrorStatus {
    domain: string;
    latency: number;
    status: 'checking' | 'online' | 'offline';
  }

  let allUsers = $state<User[]>([]);
  let appInfo = $state<any>(null);
  let editing = $state<User | null>(null);
  let editForm = $state<any>({});
  let newPassword = $state('');

  let myForm = $state<any>({});
  let myPassword = $state('');

  let bestDomain = $state('annas-archive.pk');
  let mirrorStatuses = $state<MirrorStatus[]>([
    { domain: 'annas-archive.pk', latency: 0, status: 'checking' },
    { domain: 'annas-archive.gd', latency: 0, status: 'checking' },
    { domain: 'annas-archive.gl', latency: 0, status: 'checking' },
  ]);

  async function checkLatencies() {
    mirrorStatuses.forEach((_, idx) => {
      mirrorStatuses[idx].status = 'checking';
    });

    const promises = mirrorStatuses.map(async (m, index) => {
      const start = performance.now();
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2500);
        await fetch(`https://${m.domain}/robots.txt`, {
          mode: 'no-cors',
          cache: 'no-store',
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        const duration = Math.round(performance.now() - start);
        mirrorStatuses[index] = {
          domain: m.domain,
          latency: duration,
          status: 'online'
        };
        return { domain: m.domain, duration };
      } catch {
        mirrorStatuses[index] = {
          domain: m.domain,
          latency: Infinity,
          status: 'offline'
        };
        return { domain: m.domain, duration: Infinity };
      }
    });

    const results = await Promise.all(promises);
    const valid = results.filter(r => r.duration < Infinity);
    if (valid.length > 0) {
      valid.sort((a, b) => a.duration - b.duration);
      bestDomain = valid[0].domain;
    }
  }

  onMount(async () => {
    checkLatencies();
    appInfo = await auth.appInfo();
    if ($user?.role === 'admin') {
      try {
        allUsers = await users.list();
      } catch {}
    }
    if ($user) {
      myForm = {
        username: $user.username,
        email: $user.email,
        display_name: $user.display_name,
        kindle_email: $user.kindle_email,
      };
    }
  });

  async function saveMy() {
    try {
      const data: any = { ...myForm };
      if (myPassword) data.password = myPassword;
      const u = await auth.updateMe(data);
      setUser(u);
      myPassword = '';
      toast.success($t('saved'));
    } catch (e: any) {
      let errorMsg = e.detail || $t('failed');
      if (errorMsg === 'Username already taken') {
        errorMsg = $t('username_taken');
      }
      toast.error(errorMsg);
    }
  }

  function editUser(u: User) {
    editing = u;
    editForm = { ...u };
    newPassword = '';
  }

  async function saveEdit() {
    if (!editing) return;
    try {
      const data: any = { ...editForm };
      if (newPassword) data.password = newPassword;
      const updated = await users.update(editing.id, data);
      allUsers = allUsers.map((u) => (u.id === updated.id ? updated : u));
      editing = null;
      toast.success($t('user_updated'));
    } catch (e: any) {
      toast.error(e.detail || $t('failed'));
    }
  }
</script>

<svelte:head>
  <title>{$t('settings')} — Alejandría</title>
</svelte:head>

<div class="p-6 md:p-8 max-w-3xl mx-auto">
  <h1 class="font-serif text-2xl md:text-3xl mb-6">{$t('settings')}</h1>

  {#if appInfo}
    <section class="card p-5 mb-6">
      <h2 class="text-lg font-semibold mb-3">{$t('system')}</h2>
      <dl class="text-sm space-y-1.5">
        <div class="flex justify-between">
          <dt class="text-[var(--text-muted)]">{$t('version')}</dt>
          <dd class="font-mono">{appInfo.version}</dd>
        </div>
        <div class="flex justify-between items-center">
          <dt class="text-[var(--text-muted)]">{$t('oidc')}</dt>
          <dd class="flex items-center gap-1.5">
            {#if appInfo.oidc_enabled}
              <svg class="w-4 h-4 text-[var(--success)]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span>{$t('enabled')}</span>
            {:else}
              <span>{$t('disabled')}</span>
            {/if}
          </dd>
        </div>
        <div class="flex justify-between items-center">
          <dt class="text-[var(--text-muted)]">{$t('smtp')}</dt>
          <dd class="flex items-center gap-1.5">
            {#if appInfo.smtp_configured}
              <svg class="w-4 h-4 text-[var(--success)]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span>{$t('configured')}</span>
            {:else}
              <span>{$t('not_configured')}</span>
            {/if}
          </dd>
        </div>
      </dl>
    </section>
  {/if}

  <section class="card p-5 mb-6">
    <h2 class="text-lg font-semibold mb-3">{$t('profile')}</h2>
    <div class="space-y-3">
      <div>
        <label class="block text-sm font-medium mb-1.5">{$t('username')}</label>
        <input type="text" bind:value={myForm.username} class="input" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1.5">{$t('display_name')}</label>
        <input type="text" bind:value={myForm.display_name} class="input" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1.5">{$t('email')}</label>
        <input type="email" bind:value={myForm.email} class="input" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1.5">{$t('kindle_email')}</label>
        <input type="email" bind:value={myForm.kindle_email} class="input" placeholder="you@kindle.com" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1.5">{$t('new_password')}</label>
        <input type="password" bind:value={myPassword} class="input" placeholder={$t('password_placeholder')} />
      </div>
      <button class="btn btn-primary" onclick={saveMy}>{$t('save_btn')}</button>
    </div>
  </section>

  <section class="card p-5 mb-6">
    <h2 class="text-lg font-semibold mb-3">{$t('language_label')}</h2>
    <div>
      <span class="block text-sm font-medium mb-2">{$t('language_label')} / Language</span>
      <div class="flex gap-2">
        <button
          class="btn btn-secondary flex-1"
          class:!bg-[var(--accent)]={$language === 'en'}
          class:!text-[var(--accent-text)]={$language === 'en'}
          onclick={() => setLanguage('en')}
        >English</button>
        <button
          class="btn btn-secondary flex-1"
          class:!bg-[var(--accent)]={$language === 'es'}
          class:!text-[var(--accent-text)]={$language === 'es'}
          onclick={() => setLanguage('es')}
        >Español</button>
      </div>
    </div>
  </section>

  <section class="card p-5 mb-6">
    <h2 class="text-lg font-semibold mb-3">{$t('appearance')}</h2>
    <div class="space-y-4">
      <div>
        <span class="block text-sm font-medium mb-2">{$t('app_theme')}</span>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
          {#each ['light', 'sepia', 'dark'] as tVal}
            <button
              class="btn btn-secondary"
              class:!bg-[var(--accent)]={$theme === tVal}
              class:!text-[var(--accent-text)]={$theme === tVal}
              onclick={() => setTheme(tVal)}
            >{tVal}</button>
          {/each}
          
          {#each $customThemes as ct}
            <button
              class="btn btn-secondary truncate"
              class:!bg-[var(--accent)]={$theme === ct.id}
              class:!text-[var(--accent-text)]={$theme === ct.id}
              onclick={() => setTheme(ct.id)}
              title={ct.name}
            >{ct.name}</button>
          {/each}
        </div>
      </div>
      <div>
        <span class="block text-sm font-medium mb-2">{$t('reader_theme')}</span>
        <div class="flex gap-2">
          {#each ['light', 'sepia', 'dark'] as tVal}
            <button
              class="btn btn-secondary flex-1"
              class:!bg-[var(--accent)]={$readerTheme === tVal}
              class:!text-[var(--accent-text)]={$readerTheme === tVal}
              onclick={() => setReaderTheme(tVal as any)}
            >{tVal}</button>
          {/each}
        </div>
      </div>
    </div>
  </section>

  <!-- Anna's Archive Connection Section -->
  <section class="card p-5 mb-6">
    <h2 class="text-lg font-semibold mb-3 flex items-center justify-between gap-4">
      <span>{$t('annas_archive_connection')}</span>
      <button class="btn btn-secondary !py-1 !px-2.5 text-xs flex items-center gap-1.5 shrink-0" onclick={checkLatencies}>
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
        </svg>
        {$t('test_again')}
      </button>
    </h2>
    <p class="text-xs text-[var(--text-soft)] mb-4">
      {$t('annas_archive_connection_desc')}
    </p>

    <div class="space-y-3">
      {#each mirrorStatuses as m}
        <div class="flex items-center justify-between p-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] gap-4">
          <div class="flex items-center gap-2 min-w-0">
            <span class="font-medium text-sm truncate">{m.domain}</span>
            {#if bestDomain === m.domain && m.status === 'online'}
              <span class="badge !bg-[color-mix(in_srgb,var(--accent)_15%,transparent)] !text-[var(--accent)] !border-[var(--accent)] font-semibold text-[10px] whitespace-nowrap lowercase">
                ({$t('recommended')})
              </span>
            {/if}
          </div>

          <div class="flex items-center gap-2 text-sm text-[var(--text-soft)] shrink-0">
            {#if m.status === 'checking'}
              <span class="w-2 h-2 rounded-full bg-gray-400 animate-pulse"></span>
              <span>{$t('checking')}</span>
            {:else if m.status === 'online'}
              <span class="w-2 h-2 rounded-full bg-[var(--success)]"></span>
              <span class="font-mono text-xs">{m.latency} ms</span>
            {:else}
              <span class="w-2 h-2 rounded-full bg-[var(--danger)]"></span>
              <span>{$t('offline')}</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </section>

  <!-- Custom Themes Manager Section -->
  <section class="card p-5 mb-6">
    <h2 class="text-lg font-semibold mb-3">{$t('custom_themes')}</h2>
    
    <!-- Creation Form -->
    <form onsubmit={(e) => { e.preventDefault(); handleCreateTheme(); }} class="space-y-4">
      <h3 class="text-sm font-semibold uppercase tracking-wider text-[var(--text-soft)]">{$t('create_theme')}</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium mb-1.5">{$t('theme_name')}</label>
          <input type="text" bind:value={newThemeName} class="input" placeholder="e.g. Forest Green" required />
        </div>
        
        <div>
          <label class="block text-sm font-medium mb-1.5">{$t('base_theme')}</label>
          <select bind:value={newThemeBase} class="input">
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium mb-1.5">{$t('bg_color')}</label>
          <div class="flex gap-2 items-center">
            <input type="color" bind:value={colorBg} class="h-10 w-12 border rounded cursor-pointer" />
            <input type="text" bind:value={colorBg} class="input flex-1" />
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium mb-1.5">{$t('surface_color')}</label>
          <div class="flex gap-2 items-center">
            <input type="color" bind:value={colorSurface} class="h-10 w-12 border rounded cursor-pointer" />
            <input type="text" bind:value={colorSurface} class="input flex-1" />
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium mb-1.5">{$t('border_color')}</label>
          <div class="flex gap-2 items-center">
            <input type="color" bind:value={colorBorder} class="h-10 w-12 border rounded cursor-pointer" />
            <input type="text" bind:value={colorBorder} class="input flex-1" />
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium mb-1.5">{$t('text_color')}</label>
          <div class="flex gap-2 items-center">
            <input type="color" bind:value={colorText} class="h-10 w-12 border rounded cursor-pointer" />
            <input type="text" bind:value={colorText} class="input flex-1" />
          </div>
        </div>

        <div class="md:col-span-2">
          <label class="block text-sm font-medium mb-1.5">{$t('accent_color')}</label>
          <div class="flex gap-2 items-center">
            <input type="color" bind:value={colorAccent} class="h-10 w-12 border rounded cursor-pointer" />
            <input type="text" bind:value={colorAccent} class="input flex-1" />
          </div>
        </div>
      </div>

      <button type="submit" class="btn btn-primary w-full md:w-auto">{$t('create_theme_btn')}</button>
    </form>
    
    <!-- Custom Themes List -->
    {#if $customThemes.length > 0}
      <div class="mt-6 pt-6 border-t border-[var(--border)]">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-[var(--text-soft)] mb-3">{$t('custom_themes')}</h3>
        <div class="divide-y divide-[var(--border)]">
          {#each $customThemes as ct}
            <div class="py-3 flex justify-between items-center">
              <div>
                <span class="font-medium">{ct.name}</span>
                <span class="text-xs text-[var(--text-muted)] ml-2">({ct.base})</span>
                <!-- Color Previews -->
                <div class="flex gap-1 mt-1">
                  <span class="w-4 h-4 rounded-full border border-[var(--border)]" style:background={ct.colors.bg} title="Bg"></span>
                  <span class="w-4 h-4 rounded-full border border-[var(--border)]" style:background={ct.colors.surface} title="Surface"></span>
                  <span class="w-4 h-4 rounded-full border border-[var(--border)]" style:background={ct.colors.border} title="Border"></span>
                  <span class="w-4 h-4 rounded-full border border-[var(--border)]" style:background={ct.colors.text} title="Text"></span>
                  <span class="w-4 h-4 rounded-full border border-[var(--border)]" style:background={ct.colors.accent} title="Accent"></span>
                </div>
              </div>
              <button
                class="btn btn-ghost text-[var(--danger)] hover:bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] !p-2"
                onclick={() => handleDeleteTheme(ct.id)}
                title={$t('delete_btn')}
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
              </button>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </section>

  {#if $user?.role === 'admin' && allUsers.length}
    <section class="card p-5">
      <h2 class="text-lg font-semibold mb-3">{$t('users')} ({allUsers.length})</h2>
      <div class="divide-y" style="border-color: var(--border);">
        {#each allUsers as u}
          <div class="py-3 flex items-center gap-3">
            <div class="flex-1 min-w-0">
              <div class="font-medium">{u.display_name || u.username}</div>
              <div class="text-xs text-[var(--text-muted)]">@{u.username} · {u.role} · {u.email || '—'}</div>
            </div>
            <button class="btn btn-ghost !p-2" onclick={() => editUser(u)}>
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if editing}
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4" style="background: rgba(0,0,0,0.5);">
      <div class="card p-5 w-full max-w-md">
        <h3 class="text-lg font-semibold mb-3">{$t('edit_user', { username: editing.username })}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-sm font-medium mb-1">{$t('email')}</label>
            <input type="email" bind:value={editForm.email} class="input" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">{$t('display_name')}</label>
            <input type="text" bind:value={editForm.display_name} class="input" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">{$t('role')}</label>
            <select bind:value={editForm.role} class="input">
              <option value="user">{$t('role_user')}</option>
              <option value="admin">{$t('role_admin')}</option>
              <option value="guest">{$t('role_guest')}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">{$t('new_password')}</label>
            <input type="password" bind:value={newPassword} class="input" placeholder={$t('password_placeholder')} />
          </div>
          <div class="flex items-center gap-2">
            <input id="active" type="checkbox" bind:checked={editForm.is_active} />
            <label for="active">{$t('active')}</label>
          </div>
          <div class="flex gap-2 pt-2">
            <button class="btn btn-primary flex-1" onclick={saveEdit}>{$t('save_btn')}</button>
            <button class="btn btn-secondary" onclick={() => (editing = null)}>{$t('cancel_btn')}</button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
