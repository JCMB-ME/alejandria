<script lang="ts">
  import { librarySelection, clearSelection, selectedIds, selectedCount } from '$stores/librarySelection';
  import { t } from '$stores/i18n';
  import { toast } from '$stores/toast';
  import { books, shelves } from '$api/client';
  import { confirm } from '$stores/confirm';
  import ShelfPickerModal from './ShelfPickerModal.svelte';
  import TagInputModal from './TagInputModal.svelte';

  interface Props {
    onChange: () => Promise<void> | void;
  }
  let { onChange }: Props = $props();

  let shelfOpen = $state(false);
  let shelfMode = $state<'add' | 'remove'>('add');
  let tagsOpen = $state(false);
  let tagMode = $state<'add' | 'remove' | 'set'>('add');

  let count = $derived($selectedCount);

  async function handleDelete() {
    const ids = selectedIds();
    if (ids.length === 0) return;
    const ok = await confirm({
      title: $t('bulk_delete_confirm_title', { n: ids.length }),
      message: $t('bulk_delete_confirm_body'),
      confirmLabel: $t('bulk_delete'),
    });
    if (!ok) return;
    try {
      const res = await books.bulkDelete({ book_ids: ids });
      if (res.failed && res.failed > 0) {
        toast.warning(
          $t('bulk_partial_failure', { failed: res.failed, total: ids.length }),
        );
      } else {
        toast.success($t('bulk_success_delete', { n: res.affected }));
      }
      clearSelection();
      await onChange();
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail ?? 'error';
      toast.error(detail);
    }
  }

  async function performAddToShelf(shelfId: number, shelfName: string) {
    try {
      const res = await books.bulkAddToShelf({ book_ids: selectedIds(), shelf_id: shelfId });
      if (res.failed && res.failed > 0) {
        toast.warning(
          $t('bulk_partial_failure', { failed: res.failed, total: selectedIds().length }),
        );
      } else {
        toast.success($t('bulk_success_add_shelf', { n: res.affected, shelf: shelfName }));
      }
      clearSelection();
      await onChange();
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail ?? 'error';
      toast.error(detail);
    }
  }

  async function performRemoveFromShelf(shelfId: number, shelfName: string) {
    try {
      const res = await books.bulkRemoveFromShelf({ book_ids: selectedIds(), shelf_id: shelfId });
      toast.success($t('bulk_success_remove_shelf', { n: res.affected, shelf: shelfName }));
      clearSelection();
      await onChange();
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail ?? 'error';
      toast.error(detail);
    }
  }

  async function performTagAction(tags: string[]) {
    try {
      let res;
      const n = selectedIds().length;
      const tagStr = tags.join(', ');
      if (tagMode === 'add') {
        res = await books.bulkAddTags({ book_ids: selectedIds(), tags });
        toast.success($t('bulk_success_add_tags', { n: res.affected, tags: tagStr }));
      } else if (tagMode === 'remove') {
        res = await books.bulkRemoveTags({ book_ids: selectedIds(), tags });
        toast.success($t('bulk_success_remove_tags', { n: tags.length, n_books: n }));
      } else {
        res = await books.bulkSetTags({ book_ids: selectedIds(), tags });
        toast.success($t('bulk_success_set_tags', { n: res.affected, tags: tagStr }));
      }
      clearSelection();
      await onChange();
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail ?? 'error';
      toast.error(detail);
    }
  }
</script>

{#if count > 0}
  <div
    class="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 px-4 py-2.5 rounded-full shadow-2xl border max-w-[95vw] overflow-x-auto"
    style="background: var(--surface); border-color: var(--border);"
    role="region"
    aria-label="Bulk actions"
  >
    <span class="text-sm font-medium whitespace-nowrap">
      {$t('selected_count', { n: count })}
    </span>
    <div class="h-5 w-px bg-[var(--border)]"></div>
    <button
      type="button"
      class="btn btn-secondary text-sm whitespace-nowrap"
      onclick={() => { shelfMode = 'add'; shelfOpen = true; }}
    >{$t('bulk_add_to_shelf')}</button>
    <button
      type="button"
      class="btn btn-secondary text-sm whitespace-nowrap"
      onclick={() => { tagMode = 'add'; tagsOpen = true; }}
    >{$t('bulk_add_tags')}</button>
    <button
      type="button"
      class="btn btn-secondary text-sm whitespace-nowrap"
      onclick={() => { tagMode = 'remove'; tagsOpen = true; }}
    >{$t('bulk_remove_tags')}</button>
    <button
      type="button"
      class="btn btn-secondary text-sm whitespace-nowrap"
      onclick={() => { tagMode = 'set'; tagsOpen = true; }}
    >{$t('bulk_set_tags')}</button>
    <button
      type="button"
      class="btn btn-danger text-sm whitespace-nowrap"
      onclick={handleDelete}
    >{$t('bulk_delete')}</button>
    <div class="h-5 w-px bg-[var(--border)]"></div>
    <button
      type="button"
      class="text-sm underline text-[var(--text-muted)] hover:text-[var(--text)] whitespace-nowrap"
      onclick={clearSelection}
    >{$t('deselect_all')}</button>
  </div>
{/if}

{#if shelfOpen}
  <ShelfPickerModal
    mode={shelfMode}
    onClose={() => (shelfOpen = false)}
    onPick={async (shelf) => {
      shelfOpen = false;
      if (shelfMode === 'add') {
        await performAddToShelf(shelf.id, shelf.name);
      } else {
        await performRemoveFromShelf(shelf.id, shelf.name);
      }
    }}
  />
{/if}

{#if tagsOpen}
  <TagInputModal
    mode={tagMode}
    onClose={() => (tagsOpen = false)}
    onApply={async (tags) => {
      tagsOpen = false;
      await performTagAction(tags);
    }}
  />
{/if}
