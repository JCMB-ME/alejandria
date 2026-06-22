<script lang="ts">
  import { onMount } from 'svelte';
  import { shelves as shelvesApi } from '$api/client';
  import type { Shelf } from '$api/types';
  import BookGrid from '$components/BookGrid.svelte';
  import { goto } from '$app/navigation';
  import { toast } from '$stores/toast';
  import { t, language, translateShelfName } from '$stores/i18n';

  let shelves = $state<Shelf[]>([]);
  let selected = $state<Shelf | null>(null);
  let shelfBooks = $state<any[]>([]);
  let loading = $state(false);
  let showCreate = $state(false);
  let newName = $state('');

  async function deleteSelectedShelf() {
    if (!selected) return;
    if (!confirm($t('delete_shelf_confirm'))) return;
    try {
      await shelvesApi.delete(selected.id);
      toast.success($t('shelf_deleted_success'));
      shelves = shelves.filter((s) => s.id !== selected!.id);
      selected = null;
    } catch (e: any) {
      toast.error(e.detail || $t('shelf_deleted_error'));
    }
  }



  onMount(async () => {
    shelves = await shelvesApi.list();
  });

  async function select(s: Shelf) {
    selected = s;
    loading = true;
    try {
      const data = await shelvesApi.get(s.id);
      shelfBooks = data.books || [];
    } finally {
      loading = false;
    }
  }

  async function create() {
    if (!newName.trim()) return;
    try {
      const s = await shelvesApi.create({ name: newName.trim(), shelf_type: 'manual' });
      shelves = [...shelves, { ...s, book_count: 0 } as Shelf];
      newName = '';
      showCreate = false;
    } catch (e: any) {
      toast.error(e.detail || 'Failed to create shelf');
    }
  }
</script>

<svelte:head>
  <title>{$t('shelves')} — Alejandría</title>
</svelte:head>

<div class="p-6 md:p-8 max-w-7xl mx-auto">
  <header class="mb-6 flex items-center gap-3">
    <h1 class="font-serif text-2xl md:text-3xl flex-1">{$t('shelves')}</h1>
    <button class="btn btn-primary" onclick={() => (showCreate = !showCreate)}>
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      {$t('new_shelf')}
    </button>
  </header>

  {#if showCreate}
    <div class="card p-4 mb-6 flex gap-2">
      <input
        type="text"
        bind:value={newName}
        placeholder={$t('shelf_name_placeholder')}
        class="input flex-1"
        onkeydown={(e) => e.key === 'Enter' && create()}
      />
      <button class="btn btn-primary" onclick={create}>{$t('create_btn')}</button>
      <button class="btn btn-ghost" onclick={() => (showCreate = false)}>{$t('cancel_btn')}</button>
    </div>
  {/if}

  <div class="grid md:grid-cols-[260px_1fr] gap-6">
    <aside>
      <div class="space-y-1">
        {#each shelves as s}
          <button
            class="w-full text-left p-3 rounded-lg transition-colors"
            style:background={selected?.id === s.id ? 'var(--surface)' : 'transparent'}
            onclick={() => select(s)}
          >
            <div class="flex items-center gap-2">
              {#if s.icon}
                <img src="/icons/{s.icon}.svg" alt="" class="w-5 h-5 opacity-80" />
              {:else}
                <img src="/icons/book.svg" alt="" class="w-5 h-5 opacity-60" />
              {/if}
              <span class="font-medium flex-1">{translateShelfName(s.name, $language)}</span>
              <span class="badge text-xs">{s.book_count}</span>
            </div>
            {#if s.description}
              <p class="text-xs text-[var(--text-muted)] mt-0.5 ml-7">{s.description}</p>
            {/if}
          </button>
        {/each}
      </div>
    </aside>

    <section>
      {#if !selected}
        <div class="text-center py-12 text-[var(--text-muted)]">
          <p>{$t('select_shelf_prompt')}</p>
        </div>
      {:else}
        <h2 class="text-xl font-semibold mb-4 flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            {#if selected.icon}
              <img src="/icons/{selected.icon}.svg" alt="" class="w-6 h-6 opacity-80" />
            {/if}
            {translateShelfName(selected.name, $language)}
          </div>
          {#if selected.shelf_type === 'manual'}
            <button class="btn btn-ghost text-[var(--danger)] hover:bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] flex items-center gap-1.5" onclick={deleteSelectedShelf}>
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
              {$t('delete_btn')}
            </button>
          {/if}
        </h2>
        <BookGrid books={shelfBooks} {loading} />
      {/if}
    </section>
  </div>
</div>
