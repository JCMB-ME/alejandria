<script lang="ts">
  import { onMount } from 'svelte';
  import { stats as statsApi } from '$api/client';
  import { t } from '$stores/i18n';

  let overview = $state<any>(null);
  let streak = $state<any>(null);
  let byYear = $state<Record<string, number>>({});
  let daily = $state<{ date: string; minutes: number }[]>([]);

  onMount(async () => {
    [overview, streak, byYear, daily] = await Promise.all([
      statsApi.overview(),
      statsApi.streak(),
      statsApi.byYear(),
      statsApi.daily(90),
    ]);
  });

  function maxDaily() {
    return Math.max(1, ...daily.map((d) => d.minutes));
  }
</script>

<svelte:head>
  <title>{$t('stats')} — Alejandría</title>
</svelte:head>

<div class="p-6 md:p-8 max-w-6xl mx-auto">
  <h1 class="font-serif text-2xl md:text-3xl mb-6">{$t('reading_stats')}</h1>

  {#if overview}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="card p-4">
        <div class="text-3xl font-semibold">{overview.books_finished}</div>
        <div class="text-sm text-[var(--text-muted)]">{$t('books_finished')}</div>
      </div>
      <div class="card p-4">
        <div class="text-3xl font-semibold">{overview.currently_reading}</div>
        <div class="text-sm text-[var(--text-muted)]">{$t('currently_reading')}</div>
      </div>
      <div class="card p-4">
        <div class="text-3xl font-semibold">{overview.total_reading_time_hours}h</div>
        <div class="text-sm text-[var(--text-muted)]">{$t('total_time')}</div>
      </div>
      <div class="card p-4">
        <div class="text-3xl font-semibold">{streak?.current_streak || 0}d</div>
        <div class="text-sm text-[var(--text-muted)]">{$t('current_streak')}</div>
      </div>
    </div>
  {/if}

  {#if daily.length}
    <section class="card p-4 mb-6">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)] mb-3">
        {$t('last_90_days')}
      </h2>
      <div class="flex items-end gap-0.5 h-32">
        {#each daily as d}
          <div
            class="flex-1 rounded-t transition-colors hover:opacity-80"
            style:height="{(d.minutes / maxDaily()) * 100}%"
            style:min-height="2px"
            style:background="var(--accent)"
            title="{d.date}: {d.minutes.toFixed(1)} min"
          ></div>
        {/each}
      </div>
    </section>
  {/if}

  {#if Object.keys(byYear).length}
    <section class="card p-4">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)] mb-3">
        {$t('books_by_year')}
      </h2>
      <div class="flex items-end gap-2">
        {#each Object.entries(byYear).sort() as [year, count]}
          <div class="flex-1 text-center">
            <div class="text-2xl font-semibold">{count}</div>
            <div class="text-xs text-[var(--text-muted)]">{year}</div>
          </div>
        {/each}
      </div>
    </section>
  {/if}
</div>
