<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    theme,
    getAllTagsWithCounts,
    getPathsWithTags,
    mergeTags,
    deleteTagGlobally,
    bulkAddTag,
    tags
  } from '$lib/api.js';

  let tagList = $state([]);
  let pathsWithTags = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let renameModal = $state(null);
  let mergeModal = $state(null);
  let deleteModal = $state(null);
  let createModal = $state(false);
  let renameValue = $state('');
  let mergeTarget = $state('');
  let createTagName = $state('');
  let createPaths = $state([]);
  let actionLoading = $state(false);

  $effect(() => {
    if (typeof document !== 'undefined') {
      document.body.classList.remove('light', 'dark');
      document.body.classList.add($theme);
    }
  });

  async function load() {
    loading = true;
    error = null;
    try {
      const [tagsRes, pathsRes] = await Promise.all([
        getAllTagsWithCounts(),
        getPathsWithTags()
      ]);
      tagList = tagsRes.tags || [];
      pathsWithTags = pathsRes.paths || [];
    } catch (e) {
      error = e.message;
      tagList = [];
      pathsWithTags = [];
    } finally {
      loading = false;
    }
  }

  onMount(load);

  function openRename(tag) {
    renameModal = tag;
    renameValue = tag;
  }

  async function submitRename() {
    if (!renameModal || !renameValue.trim()) return;
    actionLoading = true;
    try {
      await mergeTags(renameModal, renameValue.trim());
      renameModal = null;
      renameValue = '';
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      actionLoading = false;
    }
  }

  function openMerge(tag) {
    mergeModal = tag;
    mergeTarget = '';
  }

  async function submitMerge() {
    if (!mergeModal || !mergeTarget.trim()) return;
    actionLoading = true;
    try {
      await mergeTags(mergeModal, mergeTarget.trim());
      mergeModal = null;
      mergeTarget = '';
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      actionLoading = false;
    }
  }

  function openDelete(tag) {
    deleteModal = tag;
  }

  async function submitDelete() {
    if (!deleteModal) return;
    actionLoading = true;
    try {
      await deleteTagGlobally(deleteModal);
      deleteModal = null;
      await load();
      tags.update(() => ({}));
    } catch (e) {
      error = e.message;
    } finally {
      actionLoading = false;
    }
  }

  function openCreate() {
    createModal = true;
    createTagName = '';
    createPaths = [];
  }

  async function submitCreate() {
    const name = createTagName.trim();
    if (!name) return;
    if (!createPaths.length) {
      error = 'Select at least one path';
      return;
    }
    actionLoading = true;
    error = null;
    try {
      await bulkAddTag(name, createPaths);
      createModal = false;
      createTagName = '';
      createPaths = [];
      await load();
      tags.update(() => ({}));
    } catch (e) {
      error = e.message;
    } finally {
      actionLoading = false;
    }
  }

  function toggleCreatePath(path) {
    if (createPaths.includes(path)) {
      createPaths = createPaths.filter((p) => p !== path);
    } else {
      createPaths = [...createPaths, path];
    }
  }

  function openFilesForTag(tag) {
    goto('/?tag=' + encodeURIComponent(tag));
  }
</script>

<div class="app">
  <header class="toolbar">
    <div class="toolbar-left">
      <a href="/" class="btn">← Back to files</a>
      <button class="btn btn-primary" onclick={openCreate}>Add tag</button>
    </div>
  </header>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  <main class="content">
    <h1>Tag manager</h1>
    {#if loading}
      <p class="muted">Loading…</p>
    {:else if tagList.length === 0}
      <p class="muted">No tags yet. Add tags from the file browser or create one below.</p>
    {:else}
      <table class="tag-table">
        <thead>
          <tr>
            <th>Tag</th>
            <th>Files</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each tagList as row}
            <tr>
              <td class="tag-name">
                <button type="button" class="tag-name-btn" onclick={() => openFilesForTag(row.name)} title="Show files with this tag">{row.name}</button>
              </td>
              <td>{row.count}</td>
              <td class="actions">
                <button class="btn btn-sm" onclick={() => openRename(row.name)}>Rename</button>
                <button class="btn btn-sm" onclick={() => openMerge(row.name)}>Merge into</button>
                <button class="btn btn-sm btn-danger" onclick={() => openDelete(row.name)}>Delete</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      <div class="tag-cards">
        {#each tagList as row}
          <div class="tag-card">
            <button type="button" class="tag-card-name" onclick={() => openFilesForTag(row.name)} title="Show files with this tag">{row.name}</button>
            <span class="tag-card-count">{row.count} file(s)</span>
            <div class="tag-card-actions">
              <button class="btn btn-sm" onclick={() => openRename(row.name)}>Rename</button>
              <button class="btn btn-sm" onclick={() => openMerge(row.name)}>Merge</button>
              <button class="btn btn-sm btn-danger" onclick={() => openDelete(row.name)}>Delete</button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </main>
</div>

{#if renameModal}
  <div class="modal-overlay" onclick={() => { renameModal = null; renameValue = ''; }}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Rename tag</h3>
      <p class="modal-hint">“{renameModal}” → new name</p>
      <input
        type="text"
        bind:value={renameValue}
        placeholder="New tag name"
        onkeydown={(e) => e.key === 'Enter' && submitRename()}
      />
      <div class="modal-actions">
        <button class="btn" onclick={() => { renameModal = null; renameValue = ''; }}>Cancel</button>
        <button class="btn btn-primary" disabled={actionLoading || !renameValue.trim()} onclick={submitRename}>
          {actionLoading ? '…' : 'Rename'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if mergeModal}
  <div class="modal-overlay" onclick={() => { mergeModal = null; mergeTarget = ''; }}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Merge tag</h3>
      <p class="modal-hint">Merge “{mergeModal}” into (target tag):</p>
      <input
        type="text"
        bind:value={mergeTarget}
        placeholder="Target tag name"
        list="merge-target-list"
        onkeydown={(e) => e.key === 'Enter' && submitMerge()}
      />
      <datalist id="merge-target-list">
        {#each tagList.filter((r) => r.name !== mergeModal) as r}
          <option value={r.name} />
        {/each}
      </datalist>
      <div class="modal-actions">
        <button class="btn" onclick={() => { mergeModal = null; mergeTarget = ''; }}>Cancel</button>
        <button class="btn btn-primary" disabled={actionLoading || !mergeTarget.trim()} onclick={submitMerge}>
          {actionLoading ? '…' : 'Merge'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if deleteModal}
  <div class="modal-overlay" onclick={() => deleteModal = null}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Delete tag</h3>
      <p class="modal-hint">Remove “{deleteModal}” from all files? This cannot be undone.</p>
      <div class="modal-actions">
        <button class="btn" onclick={() => deleteModal = null}>Cancel</button>
        <button class="btn btn-danger" disabled={actionLoading} onclick={submitDelete}>
          {actionLoading ? '…' : 'Delete'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if createModal}
  <div class="modal-overlay" onclick={() => { createModal = false; createTagName = ''; createPaths = []; error = null; }}>
    <div class="modal modal-wide" onclick={(e) => e.stopPropagation()}>
      <h3>Add tag</h3>
      <p class="modal-hint">Create a new tag and assign it to paths that already have tags.</p>
      <input
        type="text"
        bind:value={createTagName}
        placeholder="Tag name"
      />
      <label class="paths-label">Paths to add this tag to:</label>
      <div class="paths-list">
        {#each pathsWithTags as path}
          <label class="path-row">
            <input type="checkbox" checked={createPaths.includes(path)} onchange={() => toggleCreatePath(path)} />
            <span class="path-text">{path}</span>
          </label>
        {/each}
      </div>
      {#if pathsWithTags.length === 0}
        <p class="muted">No paths with tags yet. Tag some files from the file browser first.</p>
      {/if}
      <div class="modal-actions">
        <button class="btn" onclick={() => { createModal = false; createTagName = ''; createPaths = []; error = null; }}>Cancel</button>
        <button
          class="btn btn-primary"
          disabled={actionLoading || !createTagName.trim() || createPaths.length === 0}
          onclick={submitCreate}
        >
          {actionLoading ? '…' : 'Add tag'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  :global(body) {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    transition: background 0.3s, color 0.3s;
  }

  :global(:root), :global(.light) {
    --bg-primary: #f5f5f5;
    --bg-secondary: #fff;
    --bg-tertiary: #fafafa;
    --text-primary: #333;
    --text-secondary: #666;
    --border-color: #e0e0e0;
    --accent-color: #2196f3;
    --accent-bg: #e3f2fd;
    --hover-bg: #f0f0f0;
    --danger-color: #f44336;
    --danger-bg: #ffebee;
    --input-bg: #fff;
  }

  :global(.dark) {
    --bg-primary: #1a1a1a;
    --bg-secondary: #2d2d2d;
    --bg-tertiary: #3a3a3a;
    --text-primary: #e0e0e0;
    --text-secondary: #aaa;
    --border-color: #444;
    --accent-color: #64b5f6;
    --accent-bg: #1e3a5f;
    --hover-bg: #3a3a3a;
    --danger-color: #ef5350;
    --danger-bg: #4a2020;
    --input-bg: #3a3a3a;
  }

  .app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    gap: 12px;
  }

  .toolbar-left {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .btn {
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 14px;
    text-decoration: none;
    transition: all 0.2s;
  }

  .btn:hover:not(:disabled) {
    background: var(--hover-bg);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-sm {
    padding: 4px 10px;
    font-size: 12px;
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .btn-primary:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-danger {
    color: var(--danger-color);
    border-color: var(--danger-color);
  }

  .btn-danger:hover:not(:disabled) {
    background: var(--danger-bg);
  }

  .error {
    padding: 12px 16px;
    background: var(--danger-bg);
    color: var(--danger-color);
  }

  .content {
    padding: 24px;
    flex: 1;
  }

  .content h1 {
    margin: 0 0 20px;
    font-size: 20px;
  }

  .muted {
    color: var(--text-secondary);
    font-size: 14px;
  }

  .tag-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--bg-secondary);
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border-color);
  }

  .tag-table th,
  .tag-table td {
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
  }

  .tag-table th {
    background: var(--bg-tertiary);
    font-weight: 600;
  }

  .tag-table tr:last-child td {
    border-bottom: none;
  }

  .tag-name {
    font-weight: 500;
  }

  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background: var(--bg-secondary);
    padding: 24px;
    border-radius: 12px;
    min-width: 400px;
    max-width: 90%;
  }

  .modal-wide {
    min-width: 480px;
    max-height: 85vh;
    overflow: auto;
  }

  .modal h3 {
    margin: 0 0 16px;
  }

  .modal-hint {
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }

  .modal input[type='text'] {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 14px;
    box-sizing: border-box;
    background: var(--input-bg);
    color: var(--text-primary);
    margin-bottom: 12px;
  }

  .paths-label {
    display: block;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }

  .paths-list {
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 8px;
    margin-bottom: 16px;
    background: var(--input-bg);
  }

  .path-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    cursor: pointer;
    font-size: 13px;
  }

  .path-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .modal-actions {
    margin-top: 16px;
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  .tag-name-btn {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    color: var(--accent-color);
    cursor: pointer;
    text-align: left;
    text-decoration: underline;
  }

  .tag-name-btn:hover {
    color: var(--text-primary);
  }

  .tag-cards {
    display: none;
  }

  .tag-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
  }

  .tag-card-name {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    padding: 0 0 4px;
    font: inherit;
    font-weight: 600;
    color: var(--accent-color);
    cursor: pointer;
    text-decoration: underline;
  }

  .tag-card-name:hover {
    color: var(--text-primary);
  }

  .tag-card-count {
    display: block;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 10px;
  }

  .tag-card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .tag-card-actions .btn {
    min-height: 44px;
  }

  @media (max-width: 768px) {
    .tag-table {
      display: none;
    }

    .tag-cards {
      display: block;
    }

    .toolbar {
      flex-wrap: wrap;
    }

    .content {
      padding: 16px;
    }

    .modal,
    .modal.modal-wide {
      min-width: 0;
      max-width: 95vw;
      max-height: 90vh;
      overflow: auto;
      padding: 16px;
    }

    .modal input[type='text'] {
      font-size: 16px;
    }

    .btn {
      min-height: 44px;
    }
  }

  .files-with-tag-list {
    margin: 0;
    padding-left: 20px;
    max-height: 300px;
    overflow-y: auto;
  }

  .files-with-tag-list li {
    margin: 4px 0;
  }

</style>
