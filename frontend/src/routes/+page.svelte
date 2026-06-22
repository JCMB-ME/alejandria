<script lang="ts">
  import { onMount } from 'svelte';
  import { library, books } from '$api/client';
  import BookGrid from '$components/BookGrid.svelte';
  import ScraperPanel from '$components/ScraperPanel.svelte';
  import type { BookSummary, LibraryStats } from '$api/types';
  import { goto } from '$app/navigation';
  import { user } from '$stores/auth';
  import { t } from '$stores/i18n';
  import { toast } from '$stores/toast';

  interface MirrorStatus {
    domain: string;
    latency: number;
    status: 'checking' | 'online' | 'offline';
  }

  let stats: LibraryStats | null = $state(null);
  let recent: BookSummary[] = $state([]);
  let loading = $state(true);
  let annasQuery = $state('');
  let bestDomain = $state('annas-archive.pk');

  // Same upload flow as /library
  let fileInput = $state<HTMLInputElement>();
  let uploading = $state(false);

  function triggerUpload() {
    fileInput?.click();
  }

  async function handleFileChange(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    uploading = true;
    toast.info($t('uploading'));
    try {
      await books.upload(file);
      toast.success($t('book_upload_success'));
      // Refresh "Recently added" so the new book shows up
      const recentRes = await books.list({ sort: 'timestamp', order: 'desc', page_size: 12 });
      recent = recentRes.items;
      stats = await library.stats();
    } catch (err: any) {
      toast.error(err.detail || $t('book_upload_error'));
    } finally {
      uploading = false;
      input.value = '';
    }
  }

  let mirrorStatuses = $state<MirrorStatus[]>([
    { domain: 'annas-archive.pk', latency: 0, status: 'checking' },
    { domain: 'annas-archive.gd', latency: 0, status: 'checking' },
    { domain: 'annas-archive.gl', latency: 0, status: 'checking' },
  ]);

  async function checkLatencies() {
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

  function searchAnnas(e: SubmitEvent) {
    e.preventDefault();
    if (annasQuery.trim()) {
      window.open(`https://${bestDomain}/search?q=${encodeURIComponent(annasQuery.trim())}`, '_blank');
    }
  }

  onMount(async () => {
    checkLatencies();
    try {
      const [statsData, recentRes] = await Promise.all([
        library.stats(),
        books.list({ sort: 'timestamp', order: 'desc', page_size: 12 })
      ]);
      stats = statsData;
      recent = recentRes.items;
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Alejandría — {$t('your_library')}</title>
</svelte:head>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
  <header class="mb-6 md:mb-8 flex flex-col md:flex-row md:items-start md:justify-between gap-3">
    <div class="min-w-0">
      <h1 class="font-serif text-2xl md:text-4xl mb-2 leading-tight">
        {$t('welcome_back')}{$user?.display_name ? `, ${$user.display_name}` : ''}
      </h1>
      <p class="text-sm md:text-base text-[var(--text-muted)]">
        {#if stats}
          {stats.total_books.toLocaleString()} {$t('books').toLowerCase()} · {stats.total_authors.toLocaleString()} {$t('authors').toLowerCase()} · {stats.total_series.toLocaleString()} {$t('series').toLowerCase()}
        {:else}
          {$t('loading')}
        {/if}
      </p>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <button class="btn btn-secondary flex items-center gap-1.5 text-sm md:text-base" onclick={triggerUpload} disabled={uploading}>
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        <span class="hidden sm:inline">{uploading ? $t('uploading') : $t('upload_book')}</span>
        <span class="sm:hidden">{$t('upload_book')}</span>
      </button>
      <input
        type="file"
        accept=".epub,.pdf,.mobi,.azw3,.azw,.fb2,.djvu,.rtf,.docx,.txt"
        class="hidden"
        bind:this={fileInput}
        onchange={handleFileChange}
      />
    </div>
  </header>

  {#if stats}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-2.5 md:gap-3 mb-6 md:mb-8">
      <div class="card p-3 md:p-4">
        <div class="text-xl md:text-2xl font-semibold">{stats.total_books.toLocaleString()}</div>
        <div class="text-xs md:text-sm text-[var(--text-muted)]">{$t('books')}</div>
      </div>
      <div class="card p-3 md:p-4">
        <div class="text-xl md:text-2xl font-semibold">{stats.total_authors.toLocaleString()}</div>
        <div class="text-xs md:text-sm text-[var(--text-muted)]">{$t('authors')}</div>
      </div>
      <div class="card p-3 md:p-4">
        <div class="text-xl md:text-2xl font-semibold">{stats.total_tags.toLocaleString()}</div>
        <div class="text-xs md:text-sm text-[var(--text-muted)]">{$t('tags')}</div>
      </div>
      <div class="card p-3 md:p-4">
        <div class="text-xl md:text-2xl font-semibold">{stats.total_series.toLocaleString()}</div>
        <div class="text-xs md:text-sm text-[var(--text-muted)]">{$t('series')}</div>
      </div>
    </div>
  {/if}

  <!-- Anna's Archive Search Integration -->
  <div class="p-4 md:p-6 mb-6 md:mb-8 bg-[var(--surface)] border border-[var(--border)] rounded-lg relative overflow-hidden flex flex-col md:flex-row md:items-center md:justify-between gap-4 md:gap-6">
    <div class="flex-1 w-full min-w-0">
      <div class="flex items-center gap-2.5 mb-2">
        <svg class="w-5 h-5 text-[var(--text)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <h3 class="text-base md:text-lg font-semibold text-[var(--text)]">{$t('annas_archive_title')}</h3>
      </div>
      <p class="text-sm text-[var(--text-soft)] max-w-xl">
        {$t('annas_archive_desc')}
      </p>

      <form onsubmit={searchAnnas} class="flex gap-2 mt-4 max-w-md">
        <input
          type="text"
          bind:value={annasQuery}
          placeholder={$t('annas_archive_placeholder')}
          class="input"
        />
        <button type="submit" class="btn btn-primary whitespace-nowrap">
          {$t('annas_archive_btn')}
        </button>
      </form>
    </div>

    <div class="flex flex-col gap-2 shrink-0 w-full md:w-auto">
      <span class="text-xs font-semibold uppercase tracking-wider text-[var(--text-soft)] mb-0.5 block md:text-right">{$t('mirrors')}</span>
      <div class="flex flex-col gap-2">
        {#each ['annas-archive.pk', 'annas-archive.gd', 'annas-archive.gl'] as domain}
          <a
            href="https://{domain}"
            target="_blank"
            rel="noopener noreferrer"
            class="btn btn-secondary hover:no-underline flex items-center justify-between gap-4 py-1.5 px-3 text-xs w-full md:min-w-[200px]"
          >
            <span class="truncate">{domain}</span>
            <svg class="w-3.5 h-3.5 opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </a>
        {/each}
      </div>
    </div>
  </div>

  <!-- Web scraper block (between annas archive and recently added) -->
  <ScraperPanel />

  <section>
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg md:text-xl font-semibold">{$t('recently_added')}</h2>
      <a href="/library?sort=timestamp&order=desc" class="text-sm text-[var(--link)] hover:underline whitespace-nowrap">
        {$t('view_all')}
      </a>
    </div>
    <BookGrid books={recent} loading={loading} />
  </section>
</div>
