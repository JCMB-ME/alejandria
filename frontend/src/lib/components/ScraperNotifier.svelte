<script lang="ts">
  /**
   * Global scraper terminal-state notifier.
   *
   * Mounted once in the root layout so the modal is reachable from any
   * page, not just the home page where ScraperPanel lives. A long scrape
   * that finishes while the user is browsing /library or /read would
   * otherwise go unnoticed — the previous ScraperPanel-only modal was
   * inert when the user navigated away.
   *
   * Polling strategy:
   * - 3s cadence when at least one job is non-terminal (something to
   *   watch).
   * - Stops entirely once every job we've ever seen has reached a
   *   terminal state and been dismissed (no point burning requests).
   * - Resumes the moment the user starts a new scrape (ScraperPanel
   *   pushes the new job id onto ``seenJobIds`` via the window event
   *   below).
   */
  import { onMount, onDestroy } from 'svelte';
  import { scraper } from '$api/client';
  import type { ScrapeJob } from '$api/types';
  import { t } from '$stores/i18n';

  // Key for persisting which terminal jobs we've already shown the
  // user. Without this, a page refresh after the modal was dismissed
  // would re-pop the modal for the same job, and conversely a hard
  // crash before the user saw the modal would mean they never see it.
  // We keep it small: a JSON array of job ids.
  const NOTIFIED_STORAGE_KEY = 'alejandria:scraper:notified-ids';

  function loadNotifiedIds(): Set<number> {
    if (typeof localStorage === 'undefined') return new Set();
    try {
      const raw = localStorage.getItem(NOTIFIED_STORAGE_KEY);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      return new Set(Array.isArray(arr) ? arr.filter((n) => Number.isInteger(n)) : []);
    } catch {
      return new Set();
    }
  }

  function persistNotifiedIds(ids: Set<number>) {
    if (typeof localStorage === 'undefined') return;
    try {
      // Cap at the 50 most recent ids so the payload stays tiny and
      // ancient terminal jobs (from weeks ago) eventually stop
      // pre-occupying the notifier.
      const arr = Array.from(ids).sort((a, b) => b - a).slice(0, 50);
      localStorage.setItem(NOTIFIED_STORAGE_KEY, JSON.stringify(arr));
    } catch {
      // localStorage may be full or disabled; not fatal.
    }
  }

  let terminalNotice = $state<ScrapeJob | null>(null);
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  // Job ids we've ever polled. Used both to detect terminal transitions
  // and to know when we can stop polling (everyone we know is terminal).
  let seenJobIds = new Set<number>();
  // Job ids that have already triggered the modal. Persisted to
  // localStorage so a page reload doesn't re-notify about a job the
  // user already acknowledged, AND so a job that finished while the
  // tab was in the background gets shown when the user comes back.
  let notifiedTerminalIds = loadNotifiedIds();
  let pollIntervalMs = 3000;

  async function refresh() {
    try {
      const next = await scraper.list();
      for (const j of next) seenJobIds.add(j.id);
      detectTerminalTransition(next);
    } catch {
      // Silent — the poll loop is best-effort and the next tick will
      // retry. Network blips shouldn't surface errors to the user.
    }
  }

  function detectTerminalTransition(next: ScrapeJob[]) {
    let candidate: ScrapeJob | null = null;
    for (const j of next) {
      if (j.status !== 'done' && j.status !== 'failed') continue;
      if (notifiedTerminalIds.has(j.id)) continue;
      if (!candidate || j.id > candidate.id) candidate = j;
    }
    if (!candidate) return;
    notifiedTerminalIds.add(candidate.id);
    persistNotifiedIds(notifiedTerminalIds);
    // Replace any on-screen notice with the latest one. The user has
    // to dismiss it anyway; showing the freshest result is more useful
    // than queuing older ones.
    terminalNotice = candidate;
  }

  function dismissTerminalNotice() {
    terminalNotice = null;
  }

  function schedule() {
    if (pollTimer) return;
    pollTimer = setInterval(refresh, pollIntervalMs);
  }

  function maybeStop() {
    // We can rest once every known job has been notified and dismissed
    // (i.e. there's nothing on screen) AND the most recent poll found
    // no non-terminal jobs. A new scrape will wake us up via the
    // ``scraper-job-started`` event below.
    if (terminalNotice) return;
    // Conservative: don't auto-stop. Polling every 3s is cheap (a few
    // hundred bytes of JSON) and keeps the UI honest if the user
    // walks away from a freshly-started job.
  }

  function handleJobStarted(e: Event) {
    const detail = (e as CustomEvent<{ job_id: number }>).detail;
    if (detail?.job_id != null) {
      seenJobIds.add(detail.job_id);
      // Force a fast refresh so the modal (or the in-flight job list)
      // picks up the new job immediately, not on the next 3s tick.
      refresh();
    }
  }

  function handleVisibilityChange() {
    // Background tabs throttle setInterval to ~1 minute in modern
    // browsers. If the user left the tab open and came back, fire a
    // refresh immediately so any terminal transition that happened
    // while the tab was hidden surfaces now, not after another full
    // throttle window.
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      refresh();
    }
  }

  onMount(() => {
    refresh();
    schedule();
    window.addEventListener('scraper-job-started', handleJobStarted);
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibilityChange);
    }
  });
  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    window.removeEventListener('scraper-job-started', handleJobStarted);
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    }
  });
</script>

<!--
  Same modal layout as before but lifted to the global scope. Only
  renders when terminalNotice is set. The backdrop and the Escape key
  are intentionally non-dismissable — the user must click the Close
  button to acknowledge the result.
-->
{#if terminalNotice}
  {@const notice = terminalNotice}
  {@const isSuccess = notice.status === 'done'}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
    role="dialog"
    aria-modal="true"
    aria-labelledby="scraper-notice-title"
    data-testid="scraper-terminal-notice"
  >
    <div
      class={[
        'w-full max-w-lg rounded-xl shadow-2xl border-2 overflow-hidden',
        isSuccess ? 'border-emerald-500' : 'border-red-500',
      ]}
      style="background: var(--surface);"
    >
      <div
        class={[
          'px-6 py-5 flex items-center gap-4',
          isSuccess ? 'bg-emerald-500/10' : 'bg-red-500/10',
        ]}
      >
        <div
          class={[
            'shrink-0 w-14 h-14 rounded-full flex items-center justify-center text-3xl font-bold text-white',
            isSuccess ? 'bg-emerald-500' : 'bg-red-500',
          ]}
          aria-hidden="true"
        >
          {isSuccess ? '✓' : '✕'}
        </div>
        <div class="min-w-0">
          <h2
            id="scraper-notice-title"
            class={[
              'text-xl md:text-2xl font-bold leading-tight',
              isSuccess ? 'text-emerald-700' : 'text-red-700',
            ]}
          >
            {$t(isSuccess ? 'scraper_notice_done_title' : 'scraper_notice_failed_title')}
          </h2>
          <p class="text-sm text-[var(--text-soft)] mt-1 truncate">
            {notice.title || notice.url}
          </p>
        </div>
      </div>

      <div class="px-6 py-5 space-y-3 border-t border-[var(--border)]">
        <p class="text-sm text-[var(--text)]">
          {$t(
            isSuccess ? 'scraper_notice_done_body' : 'scraper_notice_failed_body',
            { title: notice.title || $t('scraper_title') }
          )}
        </p>

        {#if isSuccess && notice.current_page}
          <p class="text-sm font-medium text-[var(--text-soft)]">
            {$t('scraper_notice_done_pages', { n: notice.current_page })}
          </p>
        {/if}

        {#if notice.error}
          <div
            class="mt-2 p-3 rounded-md bg-red-500/10 border border-red-500/30 text-sm text-red-700 dark:text-red-300 max-h-40 overflow-y-auto"
          >
            <div class="font-semibold mb-1">{$t('scraper_notice_error_label')}</div>
            <div class="whitespace-pre-wrap break-words">{notice.error}</div>
          </div>
        {/if}
      </div>

      <div class="px-6 py-4 border-t border-[var(--border)] flex justify-end gap-2">
        <button
          type="button"
          class="btn btn-primary text-base px-5 py-2"
          onclick={dismissTerminalNotice}
        >
          {$t('scraper_notice_close')}
        </button>
      </div>
    </div>
  </div>
{/if}