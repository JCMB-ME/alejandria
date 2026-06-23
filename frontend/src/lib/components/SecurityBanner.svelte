<script lang="ts">
  import { onMount } from 'svelte';
  import { security } from '$api/client';
  import { t } from '$stores/i18n';

  let visible = $state(false);
  let reasons = $state<string[]>([]);
  let dismissed = false;

  onMount(async () => {
    if (typeof localStorage !== 'undefined'
        && localStorage.getItem('alejandria:security-banner-dismissed') === '1') {
      dismissed = true;
    }
    try {
      const status = await security.status();
      if (status.defaults_in_use && !dismissed) {
        visible = true;
        reasons = status.reasons;
      }
    } catch {
      // Backend unreachable; don't show a broken banner.
    }
  });

  function dismiss() {
    visible = false;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('alejandria:security-banner-dismissed', '1');
    }
  }
</script>

{#if visible}
  <div
    role="alert"
    class="bg-warning/10 border-b border-warning text-text px-4 py-2 flex items-center gap-3 text-sm"
  >
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 text-warning" aria-hidden="true">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
    <span class="flex-1">
      Estás corriendo con la secret key o contraseña por defecto.
      Cámbialas antes de exponer esto a internet.
      {#if reasons.includes('default_secret') || reasons.includes('default_password')}
        <a href="/settings" class="underline ml-1">{$t('security_banner_howto')}</a>
      {/if}
    </span>
    <button
      type="button"
      class="text-muted hover:text-text leading-none"
      aria-label="Cerrar"
      onclick={dismiss}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
{/if}
