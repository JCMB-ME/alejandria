<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { scraper } from '$api/client';
  import type {
    ScrapeJob,
    ScrapeFormat,
    AdapterTestResult,
  } from '$api/types';
  import { t } from '$stores/i18n';
  import { toast } from '$stores/toast';

  // Form state
  let url = $state('');
  let formats = $state<ScrapeFormat[]>(['PDF']);
  let submitting = $state(false);
  let testing = $state(false);

  // Jobs state
  let jobs = $state<ScrapeJob[]>([]);
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  const ALL_FORMATS: ScrapeFormat[] = ['PDF', 'EPUB', 'CBZ'];

  async function refreshJobs() {
    try {
      jobs = await scraper.list();
    } catch {
      // Silent: the polling loop is best-effort.
    }
  }

  async function startJob(e: SubmitEvent) {
    e.preventDefault();
    if (!url.trim() || formats.length === 0) {
      toast.error($t('scraper_create_failed', { detail: 'missing fields' }));
      return;
    }
    submitting = true;
    try {
      const job = await scraper.create({
        url: url.trim(),
        formats,
        destinations: ['library'],
      });
      toast.success($t('scraper_create_success'));
      url = '';
      jobs = [job, ...jobs];
    } catch (err: any) {
      toast.error($t('scraper_create_failed', { detail: err?.detail || '' }));
    } finally {
      submitting = false;
    }
  }

  async function cancelJob(id: number) {
    try {
      await scraper.cancel(id);
      await refreshJobs();
    } catch (err: any) {
      toast.error(err?.detail || $t('failed'));
    }
  }

  async function testAdapter() {
    if (!url.trim()) return;
    testing = true;
    try {
      const r: AdapterTestResult = await scraper.testAdapter(url.trim());
      if (r.image_candidates.length === 0) {
        toast.warning($t('scraper_test_no_images'));
      }
      if (r.next_candidates.length === 0) {
        toast.warning($t('scraper_test_no_next'));
      }
    } catch (err: any) {
      toast.error(err?.detail || $t('failed'));
    } finally {
      testing = false;
    }
  }

  onMount(() => {
    refreshJobs();
    pollTimer = setInterval(refreshJobs, 2000);
  });
  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function fmtStatus(j: ScrapeJob): string {
    if (j.status === 'scraping') {
      return $t('scraper_status_scraping', {
        current: j.current_page,
        total: j.total_pages || '?',
      });
    }
    return $t(`scraper_status_${j.status}` as any);
  }
</script>

<section class="p-4 md:p-6 mb-6 md:mb-8 bg-[var(--surface)] border border-[var(--border)] rounded-lg">
  <h3 class="text-base md:text-lg font-semibold mb-2">{$t('scraper_title')}</h3>
  <p class="text-sm text-[var(--text-soft)] max-w-xl mb-2">
    {$t('scraper_desc')}
  </p>
  <p class="text-xs text-[var(--text-muted)] mb-4">
    {$t('scraper_copyright_notice')}
  </p>

  <form onsubmit={startJob} class="flex flex-col gap-3">
    <input
      type="url"
      bind:value={url}
      placeholder={$t('scraper_url_placeholder')}
      class="input"
      required
    />

    <div class="flex flex-wrap gap-6">
      <fieldset class="flex flex-col gap-1">
        <legend class="text-xs font-semibold uppercase tracking-wider text-[var(--text-soft)]">
          {$t('scraper_formats_label')}
        </legend>
        {#each ALL_FORMATS as f}
          <label class="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              value={f}
              bind:group={formats}
            />
            {f}
          </label>
        {/each}
      </fieldset>
    </div>
    <p class="text-xs text-[var(--text-muted)] -mt-1">
      {$t('scraper_auto_import_note')}
    </p>

    <div class="flex gap-2">
      <button type="submit" class="btn btn-primary" disabled={submitting}>
        {submitting ? $t('loading') : $t('scraper_start_btn')}
      </button>
      <button
        type="button"
        class="btn btn-secondary"
        disabled={testing || !url.trim()}
        onclick={testAdapter}
      >
        {$t('scraper_test_btn')}
      </button>
    </div>
  </form>

  <div class="mt-6">
    <h4 class="text-sm font-semibold mb-2">{$t('scraper_jobs_title')}</h4>
    {#if jobs.length === 0}
      <p class="text-sm text-[var(--text-muted)]">{$t('scraper_no_jobs')}</p>
    {:else}
      <ul class="flex flex-col gap-2">
        {#each jobs as j (j.id)}
          <li class="card p-3">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="text-sm truncate">{j.title || j.url}</div>
                <div class="text-xs text-[var(--text-muted)]">{fmtStatus(j)}</div>
                {#if j.status === 'scraping' || j.status === 'packaging'}
                  <div class="w-full h-1.5 bg-[var(--border)] rounded mt-2 overflow-hidden">
                    <div
                      class="h-full bg-[var(--link)] transition-all"
                      style:width="{j.progress_pct}%"
                    ></div>
                  </div>
                {/if}
                {#if j.error}
                  <div class="text-xs text-[var(--danger)] mt-1">{j.error}</div>
                {/if}
              </div>
              <div class="flex flex-col gap-1 shrink-0">
                {#if j.status === 'queued' || j.status === 'scraping' || j.status === 'packaging'}
                  <button
                    class="btn btn-secondary text-xs py-1 px-2"
                    onclick={() => cancelJob(j.id)}
                  >
                    {$t('scraper_cancel_btn')}
                  </button>
                {/if}
              </div>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</section>
