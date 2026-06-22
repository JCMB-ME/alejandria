<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { books as booksApi, highlights as highlightsApi, shelves, reader, auth } from '$api/client';
  import type { BookDetail, Shelf, ProgressRead } from '$api/types';
  import Cover from '$components/Cover.svelte';
  import { t, language, translateShelfName } from '$stores/i18n';
  import { toast } from '$stores/toast';

  let book = $state<BookDetail | null>(null);
  let progress = $state<ProgressRead | null>(null);
  let userShelves = $state<Shelf[]>([]);
  let shelfBookIds = $state<Record<number, number[]>>({});
  let highlights = $state<any[]>([]);
  let loading = $state(true);
  let sendToKindleSending = $state(false);
  let kindleMsg = $state('');
  let deleting = $state(false);

  // Edit metadata modal state
  let showEditModal = $state(false);
  let editTitle = $state('');
  let editAuthors = $state('');
  let editTags = $state('');
  let editSeries = $state('');
  let editSeriesIndex = $state(1.0);
  let editPublisher = $state('');
  let editPubdate = $state('');
  let editComments = $state('');
  let editRating = $state(0);
  let editCoverFile = $state<File | null>(null);
  let updating = $state(false);

  let id = $derived(parseInt($page.params.id || '0'));

  onMount(async () => {
    try {
      const [bookData, progressData, shelvesData, highlightsData] = await Promise.all([
        booksApi.get(id),
        reader.progress(id).catch(() => null),
        shelves.list().catch(() => []),
        highlightsApi.list(id).catch(() => []),
        auth.appInfo().catch(() => null),
      ]);
      book = bookData;
      progress = progressData;
      userShelves = shelvesData;
      highlights = highlightsData;

      // Fetch book_ids for each shelf to know which shelves contain this book
      const ids: Record<number, number[]> = {};
      await Promise.all(
        shelvesData.map(async (s: Shelf) => {
          try {
            const detail = await shelves.get(s.id);
            ids[s.id] = detail.book_ids || [];
          } catch {
            ids[s.id] = [];
          }
        })
      );
      shelfBookIds = ids;
    } finally {
      loading = false;
    }
  });

  function coverUrl(size: 'thumb' | 'small' | 'medium' | 'large' = 'medium') {
    return `/api/library/covers/${id}.jpg?size=${size}`;
  }

  async function sendToKindle() {
    if (!book) return;
    sendToKindleSending = true;
    kindleMsg = '';
    try {
      const res = await fetch('/api/kindle/send', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_id: book.id, target_format: 'EPUB' }),
      });
      if (res.ok) {
        kindleMsg = $t('sent_kindle_success');
      } else {
        const err = await res.json().catch(() => ({}));
        kindleMsg = err.detail || $t('sent_kindle_failed');
      }
    } catch (e: any) {
      kindleMsg = e.message || $t('sent_kindle_failed');
    } finally {
      sendToKindleSending = false;
    }
  }

  async function toggleShelf(shelf: Shelf) {
    if (!book) return;
    const bookIds = shelfBookIds[shelf.id] || [];
    const has = bookIds.includes(book.id);
    if (has) {
      await shelves.removeBook(shelf.id, book.id);
      shelfBookIds[shelf.id] = bookIds.filter((bid: number) => bid !== book!.id);
    } else {
      await shelves.addBook(shelf.id, book.id);
      shelfBookIds[shelf.id] = [...bookIds, book.id];
    }
  }

  async function deleteBook() {
    if (!book) return;
    if (!confirm($t('delete_book_confirm'))) return;
    deleting = true;
    try {
      await booksApi.delete(book.id);
      toast.success($t('book_deleted_success'));
      goto('/library');
    } catch (e: any) {
      toast.error(e.detail || $t('book_deleted_error'));
      deleting = false;
    }
  }

  function formatSize(bytes: number): string {
    const units = ['B', 'KB', 'MB', 'GB'];
    let n = bytes;
    let u = 0;
    while (n >= 1024 && u < units.length - 1) { n /= 1024; u++; }
    return `${n.toFixed(1)} ${units[u]}`;
  }

  function openEditModal() {
    if (!book) return;
    editTitle = book.title || '';
    editAuthors = (book.authors || []).map(a => a.name).join(', ');
    editTags = (book.tags || []).map(t => t.name).join(', ');
    editSeries = book.series?.name || '';
    editSeriesIndex = book.series_index ?? 1.0;
    editPublisher = book.publisher || '';
    editPubdate = book.pubdate ? new Date(book.pubdate).toISOString().split('T')[0] : '';
    editComments = book.description || book.comments || '';
    editRating = book.rating ?? 0;
    editCoverFile = null;
    showEditModal = true;
  }

  async function saveMetadata() {
    if (!book) return;
    updating = true;
    try {
      const formData = new FormData();
      formData.append('title', editTitle);
      formData.append('authors', editAuthors);
      formData.append('tags', editTags);
      formData.append('series', editSeries);
      formData.append('series_index', String(editSeriesIndex));
      formData.append('publisher', editPublisher);
      formData.append('comments', editComments);
      formData.append('rating', String(editRating));
      if (editCoverFile) {
        formData.append('cover_file', editCoverFile);
      }
      
      const updated = await booksApi.update(book.id, formData);
      book = updated;
      toast.success($t('edit_success'));
      showEditModal = false;
    } catch (e: any) {
      toast.error(e.detail || $t('edit_error'));
    } finally {
      updating = false;
    }
  }
</script>

<svelte:head>
  <title>{book?.title || $t('loading')} — Alejandría</title>
</svelte:head>

{#if loading}
  <div class="p-8 text-center text-[var(--text-muted)]">{$t('loading')}</div>
{:else if !book}
  <div class="p-8 text-center text-[var(--text-muted)]">{$t('book_not_found')}</div>
{:else}
  <div class="p-6 md:p-8 max-w-6xl mx-auto">
    <a href="/library" class="text-sm text-[var(--link)] hover:underline">{$t('back_to_library')}</a>
    <div class="mt-4 grid md:grid-cols-[280px_1fr] gap-6 md:gap-10">
      <!-- Cover -->
      <div>
        <Cover {book} size="large" class="w-full shadow-elevated rounded-lg" />
        <div class="mt-4 space-y-2">
          <a href="/read/{book.id}" target="_blank" class="btn btn-primary w-full">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
            {progress && progress.progress_pct > 0 ? $t('continue_reading', { pct: Math.round(progress.progress_pct * 100) }) : $t('read')}
          </a>
          <a href={reader.download(book.id)} class="btn btn-secondary w-full" download>
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            {$t('download')}
          </a>
          <button class="btn btn-secondary w-full" disabled={sendToKindleSending} onclick={sendToKindle}>
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            {sendToKindleSending ? $t('sending') : $t('send_to_kindle')}
          </button>
          {#if kindleMsg}
            <p class="text-sm text-center text-[var(--text-muted)]">{kindleMsg}</p>
          {/if}
        </div>
      </div>

      <!-- Metadata -->
      <div>
        <h1 class="font-serif text-3xl md:text-4xl leading-tight mb-2">{book.title}</h1>
        {#if book.authors.length}
          <p class="text-lg text-[var(--text-muted)] mb-1">
            {$t('by')}
            {#each book.authors as a, i}
              <a href="/library?author={a.id}" class="text-[var(--link)] hover:underline">{a.name}</a>{i < book.authors.length - 1 ? ', ' : ''}
            {/each}
          </p>
        {/if}
        {#if book.series}
          <p class="text-sm text-[var(--text-soft)] mb-4">
            {book.series.name} #{book.series_index?.toFixed(1) || '?'}
          </p>
        {/if}

        <div class="flex flex-wrap gap-2 mb-6">
          {#each book.formats as f}
            <span class="badge">{f.fmt} · {formatSize(f.size)}</span>
          {/each}
        </div>

        {#if book.description || book.comments}
          <div class="prose dark:prose-invert max-w-none mb-6">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)] mb-2">{$t('description')}</h2>
            <p class="whitespace-pre-wrap text-[var(--text)]">{book.description || book.comments}</p>
          </div>
        {/if}

        <details class="card p-4 mb-6">
          <summary class="cursor-pointer text-sm font-medium">{$t('details')}</summary>
          <dl class="mt-3 grid grid-cols-[120px_1fr] gap-y-2 text-sm">
            {#if book.publisher}
              <dt class="text-[var(--text-muted)]">{$t('publisher')}</dt>
              <dd>{book.publisher}</dd>
            {/if}
            {#if book.pubdate}
              <dt class="text-[var(--text-muted)]">{$t('published')}</dt>
              <dd>{new Date(book.pubdate).toLocaleDateString()}</dd>
            {/if}
            {#if book.languages.length}
              <dt class="text-[var(--text-muted)]">{$t('language_label')}</dt>
              <dd>{book.languages.join(', ')}</dd>
            {/if}
            {#if book.rating}
              <dt class="text-[var(--text-muted)]">{$t('rating')}</dt>
              <dd class="flex items-center gap-0.5">
                {#each Array(5) as _, i}
                  {#if i < book.rating}
                    <svg class="w-4 h-4 text-[var(--accent)]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linejoin="round">
                      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                  {:else}
                    <svg class="w-4 h-4 text-[var(--text-muted)]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round">
                      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                  {/if}
                {/each}
              </dd>
            {/if}
            {#if Object.keys(book.identifiers).length}
              <dt class="text-[var(--text-muted)]">{$t('identifiers')}</dt>
              <dd>
                {#each Object.entries(book.identifiers) as [k, v]}
                  <span class="badge mr-1">{k}: {v}</span>
                {/each}
              </dd>
            {/if}
          </dl>
        </details>

        {#if book.tags.length}
          <div class="mb-6">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)] mb-2">{$t('tags')}</h2>
            <div class="flex flex-wrap gap-1.5">
              {#each book.tags as t}
                <a href="/library?tag={t.id}" class="badge hover:!bg-[var(--accent)] hover:!text-[var(--accent-text)]">{t.name}</a>
              {/each}
            </div>
          </div>
        {/if}

        {#if userShelves.length}
          <div class="mb-6">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)] mb-2">{$t('shelves')}</h2>
            <div class="flex flex-wrap gap-2">
              {#each userShelves as s}
                {@const isInShelf = (shelfBookIds[s.id] || []).includes(book.id)}
                <button
                  class="btn !py-1 !px-3 text-sm flex items-center gap-1.5"
                  style:background={isInShelf ? 'var(--accent)' : ''}
                  style:color={isInShelf ? 'var(--accent-text)' : ''}
                  style:border-color={isInShelf ? 'var(--accent)' : ''}
                  onclick={() => toggleShelf(s)}
                >
                  {#if s.icon}
                    <!--
                      Render the SVG via mask-image + background-color so the
                      icon picks up currentColor from the button context.
                      A plain <img src=...> ignores currentColor (SVGs loaded
                      as external resources have no color inheritance), and
                      the previous inline `filter: brightness(10)` overwrite
                      caused the icon to go pure white in dark mode where
                      var(--accent) is also light, making it invisible. The
                      mask keeps the icon legible in all three themes
                      (light/dark/sepia) because it follows the button's
                      own color rule.
                    -->
                    <span
                      class="w-4 h-4 shrink-0 inline-block"
                      style="-webkit-mask: url(/icons/{s.icon}.svg) no-repeat center / contain; mask: url(/icons/{s.icon}.svg) no-repeat center / contain; background-color: currentColor;"
                      aria-hidden="true"
                    ></span>
                  {:else}
                    <span
                      class="w-4 h-4 shrink-0 inline-block opacity-60"
                      style="-webkit-mask: url(/icons/book.svg) no-repeat center / contain; mask: url(/icons/book.svg) no-repeat center / contain; background-color: currentColor;"
                      aria-hidden="true"
                    ></span>
                  {/if}
                  {translateShelfName(s.name, $language)}
                </button>
              {/each}
            </div>
          </div>
        {/if}

        <div class="mt-8 pt-6 flex flex-wrap gap-4" style="border-top: 1px solid var(--border);">
          <button
            class="btn btn-secondary flex items-center gap-1.5"
            onclick={openEditModal}
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            {$t('edit_details')}
          </button>
          <button
            class="btn btn-ghost text-[var(--danger)] hover:bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] flex items-center gap-1.5"
            onclick={deleteBook}
            disabled={deleting}
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
            {$t('delete_book')}
          </button>
        </div>

        {#if highlights.length}
          <div class="mt-8">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)] mb-2">
              {$t('highlights')} ({highlights.length})
            </h2>
            <div class="space-y-2">
              {#each highlights as h}
                <blockquote class="border-l-2 border-[var(--accent)] pl-3 italic text-sm">
                  {h.text}
                </blockquote>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

{#if showEditModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
    <div class="bg-[var(--surface)] text-[var(--text)] border border-[var(--border)] rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden">
      <div class="p-6 border-b border-[var(--border)] flex justify-between items-center">
        <h2 class="font-serif text-xl font-semibold">{$t('edit_details')}</h2>
        <button class="text-[var(--text-soft)] hover:text-[var(--text)]" onclick={() => (showEditModal = false)}>
          <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      
      <form onsubmit={(e) => { e.preventDefault(); saveMetadata(); }} class="flex-1 overflow-y-auto p-6 space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Title -->
          <div class="col-span-2">
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_title')}</label>
            <input type="text" class="input" bind:value={editTitle} required />
          </div>
          
          <!-- Authors -->
          <div class="col-span-2">
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_authors')}</label>
            <input type="text" class="input" bind:value={editAuthors} required />
          </div>

          <!-- Series -->
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_series')}</label>
            <input type="text" class="input" bind:value={editSeries} />
          </div>

          <!-- Series Index -->
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_series_index')}</label>
            <input type="number" step="0.1" class="input" bind:value={editSeriesIndex} />
          </div>

          <!-- Publisher -->
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_publisher')}</label>
            <input type="text" class="input" bind:value={editPublisher} />
          </div>

          <!-- Pubdate -->
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_pubdate')}</label>
            <input type="date" class="input" bind:value={editPubdate} />
          </div>

          <!-- Rating -->
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_rating')}</label>
            <select class="input text-sm" bind:value={editRating}>
              <option value={0}>0 - {$t('stars') || 'Stars'}</option>
              <option value={1}>1 - {$t('star') || 'Star'}</option>
              <option value={2}>2 - {$t('stars') || 'Stars'}</option>
              <option value={3}>3 - {$t('stars') || 'Stars'}</option>
              <option value={4}>4 - {$t('stars') || 'Stars'}</option>
              <option value={5}>5 - {$t('stars') || 'Stars'}</option>
            </select>
          </div>

          <!-- Cover Image File -->
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_cover')}</label>
            <input type="file" accept="image/*" class="input file:mr-4 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[var(--accent)] file:text-[var(--accent-text)] hover:file:bg-[var(--accent-hover)]" onchange={(e) => { const files = (e.target as HTMLInputElement).files; if (files) editCoverFile = files[0]; }} />
          </div>

          <!-- Tags -->
          <div class="col-span-2">
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_tags')}</label>
            <input type="text" class="input" bind:value={editTags} />
          </div>

          <!-- Description/Comments -->
          <div class="col-span-2">
            <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">{$t('edit_comments')}</label>
            <textarea class="input min-h-[120px]" bind:value={editComments}></textarea>
          </div>
        </div>

        <div class="pt-4 border-t border-[var(--border)] flex justify-end gap-3">
          <button type="button" class="btn btn-secondary" onclick={() => (showEditModal = false)}>
            {$t('cancel_btn')}
          </button>
          <button type="submit" class="btn btn-primary" disabled={updating}>
            {updating ? ($t('saving') || 'Saving…') : $t('save_btn')}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
