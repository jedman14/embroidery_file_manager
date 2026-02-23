<script>
  import { onMount } from 'svelte';
  import { 
    currentPath, 
    files, 
    selectedFiles, 
    loading, 
    error, 
    viewMode,
    fetchFiles,
    deleteFiles,
    moveFile,
    renameFile,
    extractZip,
    getZipContents,
    getThumbnailUrl,
    getPreviewUrl,
    getDownloadUrl,
    downloadFile,
    downloadFiles,
    createFolder,
    getFileTypeColor,
    isEmbroideryFileType,
    formatFileSize,
    theme,
    tags,
    tagSources,
    fetchTags,
    setTags,
    removeTags,
    searchByTag,
    getFilesInfo,
    getAllTags,
    suggestTags,
    runAutoTag,
    folderLogos,
    fetchFolderLogos,
    setFolderLogo,
    removeFolderLogo,
    uploadFolderLogo,
    uploadFile,
    searchCurrentThenEverywhere,
    getConvertFormats,
    convertFile,
    getEmbroideryInfo,
    getEmbroideryInfoBatch
  } from '$lib/api.js';

  let renameModal = $state(null);
  let moveModal = $state(null);
  let extractModal = $state(null);
  let previewModal = $state(null);
  let previewFile = $state(null);
  let tagModal = $state(null);
  let tagModalFile = $state(null);
  let suggestLoading = $state(false);
  let suggestError = $state(null);
  let suggestedTags = $state([]);
  let logoModal = $state(null);
  let createFolderModal = $state(null);
  let newName = $state('');
  let moveDestination = $state('');
  let extractDestination = $state('');
  let searchQuery = $state('');
  let searchType = $state('all');
  let searchSize = $state('all');
  let searchTag = $state('');
  let hoopFilter = $state('all');
  let colorChangesFilter = $state('all');
  let embroideryMetadata = $state({});
  let searchResults = $state(null); // { items, path, total } when q non-empty (current dir first, then everywhere)
  let availableTags = $state([]);
  let browsingZip = $state(null);
  let zipContents = $state([]);
  let logoUrl = $state('');
  let logoFile = $state(null);
  let logoFileInput = $state(null);
  let extractFolders = $state([]);
  let renameFolderModal = $state(null);
  let renameFolderName = $state('');
  let autoTagLoading = $state(false);
  let autoTagResult = $state(null); // { processed, skipped, errors } or null
  let tagFilter = $state(null); // when set, view shows only files with this tag (same UX as folder)
  let tagViewFiles = $state([]);
  let tagViewLoading = $state(false);
  let previewEmbroideryInfo = $state(null); // { color_count, colors: [{ hex, catalog_number?, description? }] }
  let previewEmbroideryLoading = $state(false);
  let previewEmbroideryError = $state(null);
  let convertModalFile = $state(null);
  let convertTargetFormat = $state('.dst');
  let convertSavePath = $state('');
  let convertAction = $state('download'); // 'download' | 'save'
  let convertFormats = $state({ readable: [], writable: [] });
  let convertLoading = $state(false);
  let convertError = $state(null);

  $effect(() => {
    if (typeof document !== 'undefined') {
      document.body.classList.remove('light', 'dark');
      document.body.classList.add($theme);
    }
  });

  async function handleZipClick(file) {
    if (file.is_zip) {
      try {
        const result = await getZipContents(file.path);
        browsingZip = file.path;
        zipContents = result.items.map(item => ({
          ...item,
          file_type: file.file_type,
          is_directory: item.is_directory
        }));
        files.set(zipContents);
        currentPath.set(file.path + '/');
      } catch (e) {
        error.set(e.message);
      }
    }
  }

  let filteredFiles = $derived(
    $files.filter(f => {
      const nameMatch = f.name.toLowerCase().includes(searchQuery.toLowerCase());
      
      let typeMatch = true;
      if (searchType !== 'all') {
        typeMatch = f.file_type?.toLowerCase() === searchType.toLowerCase();
      }
      
      let sizeMatch = true;
      if (searchSize === 'small') sizeMatch = f.size < 100000;
      else if (searchSize === 'medium') sizeMatch = f.size >= 100000 && f.size < 1000000;
      else if (searchSize === 'large') sizeMatch = f.size >= 1000000;
      
      let tagMatch = true;
      if (searchTag) {
        const fileTags = $tags[f.path] || [];
        tagMatch = fileTags.some(t => t.toLowerCase().includes(searchTag.toLowerCase()));
      }
      
      return nameMatch && typeMatch && sizeMatch && tagMatch;
    })
  );

  let listBeforeHoopFilter = $derived.by(() => {
    if (tagFilter) {
      const list = tagViewFiles;
      return list.filter(f => {
        const typeMatch = searchType === 'all' || f.file_type?.toLowerCase() === searchType.toLowerCase();
        const sizeMatch = searchSize === 'all' || (searchSize === 'small' && f.size < 100000) || (searchSize === 'medium' && f.size >= 100000 && f.size < 1000000) || (searchSize === 'large' && f.size >= 1000000);
        const tagMatch = !searchTag || ($tags[f.path] || []).some(t => t.toLowerCase().includes(searchTag.toLowerCase()));
        return typeMatch && sizeMatch && tagMatch;
      });
    }
    if (searchResults) {
      return searchResults.items.filter(f => {
        const typeMatch = searchType === 'all' || f.file_type?.toLowerCase() === searchType.toLowerCase();
        const sizeMatch = searchSize === 'all' || (searchSize === 'small' && f.size < 100000) || (searchSize === 'medium' && f.size >= 100000 && f.size < 1000000) || (searchSize === 'large' && f.size >= 1000000);
        const tagMatch = !searchTag || ($tags[f.path] || []).some(t => t.toLowerCase().includes(searchTag.toLowerCase()));
        return typeMatch && sizeMatch && tagMatch;
      });
    }
    return filteredFiles;
  });

  function fitsInHoop(widthIn, heightIn, hoopKey) {
    if (hoopKey === 'all') return true;
    const parts = hoopKey.split('x').map(Number);
    if (parts.length !== 2 || parts.some(isNaN)) return true;
    const [maxW, maxH] = parts;
    const dMin = Math.min(widthIn, heightIn), dMax = Math.max(widthIn, heightIn);
    const hMin = Math.min(maxW, maxH), hMax = Math.max(maxW, maxH);
    return dMin <= hMin && dMax <= hMax;
  }

  let displayFiles = $derived.by(() => {
    const list = listBeforeHoopFilter;
    const hoop = hoopFilter;
    const colorCap = colorChangesFilter;
    const meta = embroideryMetadata;
    return list.filter(f => {
      if (f.is_directory || f.is_zip || !isEmbroideryFileType(f.file_type)) return true;
      const m = meta[f.path];
      if (!m) return true;
      if (hoop !== 'all' && !fitsInHoop(m.width_in || 0, m.height_in || 0, hoop)) return false;
      if (colorCap !== 'all') {
        const cap = parseInt(colorCap, 10);
        if (!isNaN(cap) && (m.color_changes ?? 0) > cap) return false;
      }
      return true;
    });
  });

  $effect(() => {
    const list = listBeforeHoopFilter;
    const paths = list.filter(f => !f.is_directory && !f.is_zip && isEmbroideryFileType(f.file_type)).map(f => f.path);
    if (paths.length === 0) {
      embroideryMetadata = {};
      return;
    }
    getEmbroideryInfoBatch(paths).then((r) => {
      const items = r.items || [];
      embroideryMetadata = Object.fromEntries(items.map((i) => [i.path, i]));
    }).catch(() => { embroideryMetadata = {}; });
  });

  $effect(() => {
    const q = searchQuery.trim();
    if (!q) {
      searchResults = null;
      return;
    }
    let cancelled = false;
    const t = setTimeout(() => {
      searchCurrentThenEverywhere(q, $currentPath, 500).then((data) => {
        if (!cancelled) searchResults = data;
      }).catch(() => { if (!cancelled) searchResults = { items: [], path: '', total: 0 }; });
    }, 320);
    return () => { cancelled = true; clearTimeout(t); };
  });

  async function openTagView(tag) {
    tagFilter = tag;
    tagViewFiles = [];
    tagViewLoading = true;
    selectedFiles.set(new Set());
    try {
      const data = await searchByTag(tag);
      const results = data.results || [];
      const pathToTags = {};
      const pathToSources = {};
      for (const r of results) {
        pathToTags[r.path] = r.tags || [];
        pathToSources[r.path] = r.tag_sources || {};
      }
      tags.update((t) => ({ ...t, ...pathToTags }));
      tagSources.update((s) => ({ ...s, ...pathToSources }));
      if (results.length === 0) {
        tagViewFiles = [];
      } else {
        const { items } = await getFilesInfo(results.map((r) => r.path));
        tagViewFiles = items || [];
      }
      if (typeof history !== 'undefined' && history.replaceState) {
        const url = new URL(window.location.href);
        url.searchParams.set('tag', tag);
        history.replaceState({}, '', url.pathname + '?' + url.searchParams.toString());
      }
    } catch (e) {
      tagViewFiles = [];
    } finally {
      tagViewLoading = false;
    }
  }

  function clearTagView() {
    tagFilter = null;
    tagViewFiles = [];
    selectedFiles.set(new Set());
    if (typeof history !== 'undefined' && history.replaceState) {
      const url = new URL(window.location.href);
      url.searchParams.delete('tag');
      const qs = url.searchParams.toString();
      history.replaceState({}, '', qs ? url.pathname + '?' + qs : url.pathname);
    }
    fetchFiles($currentPath);
  }

  onMount(async () => {
    const tagFromUrl = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('tag');
    if (tagFromUrl) {
      await openTagView(tagFromUrl);
    } else {
      const storedPath = currentPath.get();
      fetchFiles(storedPath || '');
    }
    const allTags = await getAllTags();
    availableTags = allTags.tags;
    await fetchFolderLogos();
  });

  function navigateToFolder(path) {
    tagFilter = null;
    tagViewFiles = [];
    searchResults = null;
    if (browsingZip && path === '') {
      fetchFiles(browsingZip.split('/').slice(0, -1).join('/'));
      browsingZip = null;
      zipContents = [];
    } else {
      browsingZip = null;
      zipContents = [];
      fetchFiles(path);
    }
  }

  function navigateUp() {
    if (tagFilter) {
      clearTagView();
      return;
    }
    searchResults = null;
    if (browsingZip) {
      const parentPath = browsingZip.split('/').slice(0, -1).join('/');
      fetchFiles(parentPath || '');
      browsingZip = null;
      zipContents = [];
      return;
    }
    const parts = $currentPath.split('/').filter(Boolean);
    parts.pop();
    fetchFiles(parts.join('/'));
  }

  function toggleSelect(path) {
    selectedFiles.update(s => {
      const newSet = new Set(s);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return newSet;
    });
  }

  function selectAll() {
    const list = tagFilter ? tagViewFiles : (searchResults ? searchResults.items : $files);
    if ($selectedFiles.size === list.length) {
      selectedFiles.set(new Set());
    } else {
      selectedFiles.set(new Set(list.map(f => f.path)));
    }
  }

  function handleContextMenu(e, file) {
    e.preventDefault();
    if (file.is_directory) {
      navigateToFolder(file.path);
    }
  }

  async function handleRename() {
    if (!renameModal || !newName) return;
    await renameFile(renameModal, newName);
    renameModal = null;
    newName = '';
    if (tagFilter) await openTagView(tagFilter);
    else fetchFiles($currentPath);
  }

  async function handleMove() {
    if (!moveModal || !moveDestination) return;
    await moveFile(moveModal, moveDestination);
    moveModal = null;
    moveDestination = '';
    if (tagFilter) await openTagView(tagFilter);
    else fetchFiles($currentPath);
  }

  async function handleDelete() {
    if ($selectedFiles.size === 0) return;
    if (!confirm(`Delete ${$selectedFiles.size} item(s)?`)) return;
    try {
      await deleteFiles([...$selectedFiles]);
      searchResults = null;
      if (tagFilter) await openTagView(tagFilter);
      else fetchFiles($currentPath);
    } catch (_) {}
  }

  async function handleDeleteOne(file) {
    const label = file.is_directory ? `folder "${file.name}" and its contents` : `file "${file.name}"`;
    if (!confirm(`Delete ${label}?`)) return;
    try {
      await deleteFiles([file.path]);
      searchResults = null;
      if (tagFilter) await openTagView(tagFilter);
      else fetchFiles($currentPath);
    } catch (_) {}
  }

  async function openExtractModal(file) {
    extractModal = file.path;
    extractDestination = $currentPath;
    try {
      const apiBase = (typeof import.meta.env.VITE_API_URL === 'string' && import.meta.env.VITE_API_URL) || '';
      const resp = await fetch(`${apiBase}/api/files?path=${encodeURIComponent($currentPath)}`);
      const data = await resp.json();
      extractFolders = data.items.filter(i => i.is_directory);
    } catch { extractFolders = []; }
  }

  async function handleExtract() {
    if (!extractModal) return;
    await extractZip(extractModal, extractDestination);
    extractModal = null;
    extractDestination = '';
    fetchFiles($currentPath);
  }

  function openTagModal(file) {
    tagModal = file.path;
    tagModalFile = file;
    suggestError = null;
    suggestedTags = [];
    fetchTags(file.path);
  }

  async function handleSuggestFromImage() {
    if (!tagModal) return;
    suggestLoading = true;
    suggestError = null;
    suggestedTags = [];
    try {
      const data = await suggestTags(tagModal);
      suggestedTags = data.tags || [];
    } catch (e) {
      suggestError = e.message;
    } finally {
      suggestLoading = false;
    }
  }

  async function handleAddSuggestedTag(tag) {
    if (!tagModal) return;
    const currentFileTags = $tags[tagModal] || [];
    if (!currentFileTags.includes(tag)) {
      await setTags(tagModal, [...currentFileTags, tag]);
    }
    suggestedTags = suggestedTags.filter(t => t !== tag);
  }

  async function handleAddAllSuggested() {
    if (!tagModal || suggestedTags.length === 0) return;
    const currentFileTags = $tags[tagModal] || [];
    const merged = [...new Set([...currentFileTags, ...suggestedTags])];
    await setTags(tagModal, merged);
    suggestedTags = [];
  }

  async function handleAddTag(tagInput) {
    if (!tagModal || !tagInput) return;
    const currentFileTags = $tags[tagModal] || [];
    if (!currentFileTags.includes(tagInput)) {
      await setTags(tagModal, [...currentFileTags, tagInput]);
    }
    fetchFiles($currentPath);
  }

  async function handleRemoveTag(tag) {
    if (!tagModal) return;
    const currentFileTags = $tags[tagModal] || [];
    await setTags(tagModal, currentFileTags.filter(t => t !== tag));
    if (tagFilter) await openTagView(tagFilter);
    else fetchFiles($currentPath);
  }

  let fileInput;
  
  async function handleUpload(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    for (const file of files) {
      const filePath = $currentPath ? `${$currentPath}/${file.name}` : file.name;
      await uploadFile(filePath, file);
    }
    
    fetchFiles($currentPath);
    e.target.value = '';
  }

  function openRenameModal(file) {
    renameModal = file.path;
    newName = file.name;
  }

  function openMoveModal(file) {
    moveModal = file.path;
    moveDestination = $currentPath;
  }

  function openPreviewModal(file) {
    previewFile = file;
    previewModal = true;
    previewEmbroideryInfo = null;
    previewEmbroideryError = null;
    previewEmbroideryLoading = false;
    fetchTags(file.path);
    if (file && !file.is_directory && !file.is_zip && isEmbroideryFileType(file.file_type)) {
      previewEmbroideryLoading = true;
      getEmbroideryInfo(file.path)
        .then((data) => {
          previewEmbroideryInfo = data;
          previewEmbroideryError = null;
        })
        .catch((err) => {
          previewEmbroideryError = err?.message || 'Color info unavailable';
        })
        .finally(() => {
          previewEmbroideryLoading = false;
        });
    }
  }

  function openLogoModal(file) {
    logoModal = file.path;
    logoUrl = $folderLogos[file.path] || '';
    logoFile = null;
  }

  function getConvertSavePathDefault() {
    if (!convertModalFile) return '';
    const base = convertModalFile.name.replace(/\.[^.]+$/, '');
    const dir = $currentPath ? $currentPath + '/' : '';
    return `${dir}${base}_converted${convertTargetFormat}`;
  }

  async function openConvertModal(file) {
    if (file.is_directory || file.is_zip) return;
    convertModalFile = file;
    convertError = null;
    try {
      const formats = await getConvertFormats();
      convertFormats = formats;
      const ext = file.name.includes('.') ? '.' + file.name.split('.').pop().toLowerCase() : '';
      const writable = (formats.writable || []).filter((e) => e !== ext);
      convertTargetFormat = writable.length ? writable[0] : (formats.writable && formats.writable[0]) || '.dst';
      convertSavePath = getConvertSavePathDefault();
      convertAction = 'download';
    } catch (e) {
      convertError = e.message;
    }
  }

  async function handleConvert() {
    if (!convertModalFile) return;
    convertLoading = true;
    convertError = null;
    try {
      const dest = convertAction === 'save' ? convertSavePath : null;
      await convertFile(convertModalFile.path, convertTargetFormat, dest);
      convertModalFile = null;
      if (dest) fetchFiles($currentPath);
    } catch (e) {
      convertError = e.message;
      return;
    } finally {
      convertLoading = false;
    }
  }

  function isConvertibleFile(file) {
    return file && !file.is_directory && !file.is_zip && isEmbroideryFileType(file.file_type);
  }

  async function handleSetLogo() {
    if (!logoModal) return;
    if (logoFile) {
      await uploadFolderLogo(logoModal, logoFile);
    } else if (logoUrl.trim()) {
      await setFolderLogo(logoModal, logoUrl.trim());
    } else {
      await removeFolderLogo(logoModal);
    }
    logoModal = null;
    logoUrl = '';
    logoFile = null;
    await fetchFolderLogos();
  }

  function handleLogoFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
      logoFile = file;
      logoUrl = '';
    }
  }

  async function handleCreateFolder() {
    if (!createFolderModal || !newName) return;
    const folderPath = createFolderModal ? `${createFolderModal}/${newName}` : newName;
    await createFolder(folderPath);
    createFolderModal = null;
    newName = '';
    fetchFiles($currentPath);
  }

  async function handleRunAutoTag() {
    autoTagLoading = true;
    autoTagResult = null;
    error.set(null);
    try {
      const r = await runAutoTag($currentPath);
      autoTagResult = r;
      fetchFiles($currentPath);
      const allTags = await getAllTags();
      availableTags = allTags.tags;
    } catch (e) {
      error.set(e.message);
    } finally {
      autoTagLoading = false;
    }
  }
</script>

<div class="app">
  <header class="toolbar">
    <div class="toolbar-left">
      <button class="btn" onclick={navigateUp} disabled={!$currentPath}>↑ Up</button>
      <button class="btn" onclick={() => tagFilter ? openTagView(tagFilter) : fetchFiles($currentPath)}>↻ Refresh</button>
      <button class="btn" onclick={() => fileInput.click()}>⬆️ Upload</button>
      <button class="btn" onclick={() => createFolderModal = $currentPath}>📁+ New Folder</button>
      <button 
        class="btn" 
        onclick={handleRunAutoTag} 
        disabled={autoTagLoading}
        title="Tag untagged embroidery files (current folder and subfolders)"
      >
        {autoTagLoading ? '…' : '🏷️ Auto-tag untagged'}
      </button>
      <a href="/tags" class="btn" title="Manage all tags">Tag manager</a>
      <input 
        type="file" 
        multiple 
        style="display: none" 
        bind:this={fileInput} 
        onchange={handleUpload}
      />
      <input 
        type="text" 
        class="search search-main" 
        placeholder="Search by name, path, or tags…" 
        bind:value={searchQuery}
        title="Searches file names, folder paths, and tags. Results are ranked by relevance."
      />
      <select class="filter-select" bind:value={searchType}>
        <option value="all">All Types</option>
        <option value="Tajima">DST (Tajima)</option>
        <option value="Brother">PES (Brother)</option>
        <option value="Melco">EXP (Melco)</option>
        <option value="Viking">VP3 (Viking)</option>
        <option value="Janome">JEF (Janome)</option>
        <option value="Wilcom">XXX (Wilcom)</option>
      </select>
      <select class="filter-select" bind:value={searchSize}>
        <option value="all">Any Size</option>
        <option value="small">&lt; 100KB</option>
        <option value="medium">100KB - 1MB</option>
        <option value="large">&gt; 1MB</option>
      </select>
      <input 
        type="text" 
        class="search" 
        placeholder="Filter by tag..." 
        bind:value={searchTag}
      />
      <select class="filter-select" bind:value={hoopFilter} title="Show only files that fit in this hoop or smaller">
        <option value="all">Hoop: Any</option>
        <option value="4x4">Up to 4×4 in</option>
        <option value="5x7">Up to 5×7 in</option>
        <option value="6x10">Up to 6×10 in</option>
        <option value="8x8">Up to 8×8 in</option>
        <option value="9x12">Up to 9×12 in</option>
      </select>
      <select class="filter-select" bind:value={colorChangesFilter} title="Show only files with this many color changes or fewer">
        <option value="all">Color changes: Any</option>
        <option value="3">Up to 3</option>
        <option value="5">Up to 5</option>
        <option value="10">Up to 10</option>
        <option value="20">Up to 20</option>
      </select>
    </div>
    <div class="toolbar-right">
      <button class="btn" onclick={() => theme.toggle()}>
        {$theme === 'dark' ? '☀️' : '🌙'}
      </button>
      <button 
        class="btn" 
        onclick={() => downloadFiles([...$selectedFiles])}
        disabled={$selectedFiles.size === 0}
      >
        ⬇️ Download ({$selectedFiles.size})
      </button>
      <button 
        class="btn btn-danger" 
        onclick={handleDelete}
        disabled={$selectedFiles.size === 0}
      >
        Delete ({$selectedFiles.size})
      </button>
      <button 
        class="btn" 
        class:active={$viewMode === 'grid'}
        onclick={() => viewMode.set('grid')}
      >▦ Grid</button>
      <button 
        class="btn" 
        class:active={$viewMode === 'list'}
        onclick={() => viewMode.set('list')}
      >☰ List</button>
    </div>
  </header>

  {#if $error}
    <div class="error">{$error}</div>
  {/if}

  <div class="breadcrumb">
    {#if tagFilter}
      <span class="breadcrumb-item">Tag: <strong>{tagFilter}</strong></span>
      <button class="btn btn-sm breadcrumb-clear" onclick={clearTagView}>← Back to folder</button>
    {:else}
      <button class="breadcrumb-item" onclick={() => fetchFiles('')}>Root</button>
      {#each $currentPath.split('/').filter(Boolean) as part, i}
        <span class="breadcrumb-sep">/</span>
        <button 
          class="breadcrumb-item" 
          onclick={() => fetchFiles($currentPath.split('/').slice(0, i + 1).join('/'))}
        >
          {part}
        </button>
      {/each}
      {#if browsingZip}
        <span class="breadcrumb-sep">/</span>
        <span class="breadcrumb-item browsing">📦 Inside ZIP</span>
      {/if}
    {/if}
  </div>

  <div class="toolbar-secondary">
    <label class="select-all">
      <input 
        type="checkbox" 
        checked={$selectedFiles.size === displayFiles.length && displayFiles.length > 0}
        onchange={selectAll}
      />
      Select All
    </label>
    <span class="secondary-hint">Select files or folders (checkbox), then Delete or Download.</span>
    <span class="file-count">
      {#if tagFilter}
        {tagViewFiles.length} files with tag
      {:else if searchResults}
        {searchResults.total} search results
      {:else}
        {$files.length} items
      {/if}
    </span>
  </div>

  {#if $loading || (tagFilter && tagViewLoading)}
    <div class="loading">Loading...</div>
  {:else if tagFilter && displayFiles.length === 0}
    <div class="search-empty">
      <p>No files with tag <strong>"{tagFilter}"</strong>.</p>
      <button class="btn" onclick={clearTagView}>← Back to folder</button>
    </div>
  {:else if searchResults && displayFiles.length === 0}
    <div class="search-empty">
      <p>No results for <strong>"{searchQuery.trim()}"</strong>.</p>
      <p class="search-empty-hint">Try different words, check scope (Current vs Everywhere), or enable <strong>Fuzzy</strong> for typo-tolerant search.</p>
    </div>
  {:else if $viewMode === 'grid'}
    <div class="file-grid">
      {#each displayFiles as file}
        <div 
          class="file-card" 
          class:selected={$selectedFiles.has(file.path)}
          onclick={() => {
            if (file.is_directory || file.is_zip) {
              if (file.is_zip) {
                handleZipClick(file);
              } else {
                navigateToFolder(file.path);
              }
            } else {
              openPreviewModal(file);
            }
          }}
          ondblclick={() => !file.is_directory && (openRenameModal(file))}
          oncontextmenu={(e) => handleContextMenu(e, file)}
        >
          <div class="file-checkbox" onclick={(e) => { e.stopPropagation(); toggleSelect(file.path); }}>
            <input 
              type="checkbox" 
              checked={$selectedFiles.has(file.path)}
              onclick={(e) => e.stopPropagation()}
            />
          </div>
          <div class="file-thumb">
            {#if file.is_directory}
              {#if $folderLogos[file.path]}
                <img 
                  src={$folderLogos[file.path]} 
                  alt={file.name}
                  class="folder-logo"
                  onerror={(e) => e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23e0e0e0" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%23666" font-size="40">📁</text></svg>'}
                />
              {:else}
                <span class="icon folder">📁</span>
              {/if}
            {:else if file.is_zip}
              <span class="icon zip">📦</span>
            {:else}
              <img 
                src={getThumbnailUrl(file.path)} 
                alt={file.name}
                onerror={(e) => e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23e0e0e0" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%23666" font-size="40">?</text></svg>'}
              />
            {/if}
          </div>
          <div class="file-name" title={file.name}>{file.name}</div>
          {#if ($tags[file.path] || []).length > 0}
            <div class="file-tags">
              {#each ($tags[file.path] || []).slice(0, 4) as tag}
                {@const src = ($tagSources[file.path] || {})[tag]}
                <span class="file-tag-pill clickable" role="button" tabindex="0" title={src === 'auto' ? 'Auto-tagged · Click to show all' : 'Manual · Click to show all'} onclick={(e) => { e.stopPropagation(); openTagView(tag); }} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openTagView(tag); } }}>{tag}{#if src === 'auto'}<span class="tag-source-badge" aria-label="Auto-tagged">auto</span>{/if}</span>
              {/each}
              {#if ($tags[file.path] || []).length > 4}
                <span class="file-tag-pill more">+{($tags[file.path] || []).length - 4}</span>
              {/if}
            </div>
          {/if}
          {#if searchResults && file.path}
            <div class="file-path-hint" title={file.path}>{file.path}</div>
          {/if}
          <div class="file-info">
            <span class="file-type" style="color: {getFileTypeColor(file.file_type)}">
              {file.file_type}
            </span>
            <span class="file-size">{formatFileSize(file.size)}</span>
          </div>
          {#if file.is_zip}
            <button class="extract-btn" onclick={(e) => { e.stopPropagation(); openExtractModal(file); }}>
              Extract
            </button>
          {/if}
          <div class="file-actions">
            {#if isConvertibleFile(file)}
              <button onclick={(e) => { e.stopPropagation(); openConvertModal(file); }} title="Convert format">🔄</button>
            {/if}
            <button onclick={(e) => { e.stopPropagation(); openTagModal(file); }} title="Tags">🏷️</button>
            <button onclick={(e) => { e.stopPropagation(); openRenameModal(file); }} title="Rename">✏️</button>
            <button onclick={(e) => { e.stopPropagation(); openMoveModal(file); }} title="Move">📁</button>
            {#if file.is_directory}
              <button onclick={(e) => { e.stopPropagation(); openLogoModal(file); }} title="Folder logo">🖼️</button>
            {/if}
            <button class="action-delete" onclick={(e) => { e.stopPropagation(); handleDeleteOne(file); }} title={file.is_directory ? 'Delete folder' : 'Delete file'}>🗑️</button>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="file-list">
      <div class="list-header">
        <span class="col-select"></span>
        <span class="col-name">Name</span>
        <span class="col-tags">Tags</span>
        <span class="col-type">Type</span>
        <span class="col-size">Size</span>
        <span class="col-actions">Actions</span>
      </div>
      {#each displayFiles as file}
        <div 
          class="list-row" 
          class:selected={$selectedFiles.has(file.path)}
          onclick={() => {
            if (file.is_zip) {
              handleZipClick(file);
            } else if (file.is_directory) {
              navigateToFolder(file.path);
            }
          }}
        >
          <span class="col-select">
            <input 
              type="checkbox" 
              checked={$selectedFiles.has(file.path)}
              onclick={(e) => { e.stopPropagation(); toggleSelect(file.path); }}
            />
          </span>
          <span class="col-name">
            {#if file.is_directory}
              📁
            {:else if file.is_zip}
              📦
            {:else}
              🧵
            {/if}
            {file.name}
            {#if searchResults && file.path}
              <span class="list-path-hint" title={file.path}> ({file.path})</span>
            {/if}
          </span>
          <span class="col-tags">
            {#each ($tags[file.path] || []).slice(0, 3) as tag}
              {@const src = ($tagSources[file.path] || {})[tag]}
              <span class="file-tag-pill clickable" role="button" tabindex="0" title={src === 'auto' ? 'Auto-tagged · Click to show all' : 'Manual · Click to show all'} onclick={(e) => { e.stopPropagation(); openTagView(tag); }} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openTagView(tag); } }}>{tag}{#if src === 'auto'}<span class="tag-source-badge" aria-label="Auto-tagged">auto</span>{/if}</span>
            {/each}
          </span>
          <span class="col-type" style="color: {getFileTypeColor(file.file_type)}">
            {file.file_type}
          </span>
          <span class="col-size">{formatFileSize(file.size)}</span>
          <span class="col-actions">
            {#if isConvertibleFile(file)}
              <button onclick={(e) => { e.stopPropagation(); openConvertModal(file); }} title="Convert format">🔄</button>
            {/if}
            <button onclick={(e) => { e.stopPropagation(); openTagModal(file); }} title="Tags">🏷️</button>
            <button onclick={(e) => { e.stopPropagation(); openRenameModal(file); }} title="Rename">✏️</button>
            <button onclick={(e) => { e.stopPropagation(); openMoveModal(file); }} title="Move">📁</button>
            {#if file.is_zip}
              <button onclick={(e) => { e.stopPropagation(); openExtractModal(file); }} title="Extract">📦</button>
            {/if}
            {#if file.is_directory}
              <button onclick={(e) => { e.stopPropagation(); openLogoModal(file); }} title="Folder logo">🖼️</button>
            {/if}
            <button class="action-delete" onclick={(e) => { e.stopPropagation(); handleDeleteOne(file); }} title={file.is_directory ? 'Delete folder' : 'Delete file'}>🗑️</button>
          </span>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if renameModal}
  <div class="modal-overlay" onclick={() => renameModal = null}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Rename File</h3>
      <input 
        type="text" 
        bind:value={newName} 
        placeholder="New name"
        onkeydown={(e) => e.key === 'Enter' && handleRename()}
      />
      <div class="modal-actions">
        <button class="btn" onclick={() => renameModal = null}>Cancel</button>
        <button class="btn btn-primary" onclick={handleRename}>Rename</button>
      </div>
    </div>
  </div>
{/if}

{#if moveModal}
  <div class="modal-overlay" onclick={() => moveModal = null}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Move File</h3>
      <input 
        type="text" 
        bind:value={moveDestination} 
        placeholder="Destination path"
        onkeydown={(e) => e.key === 'Enter' && handleMove()}
      />
      <div class="modal-actions">
        <button class="btn" onclick={() => moveModal = null}>Cancel</button>
        <button class="btn btn-primary" onclick={handleMove}>Move</button>
      </div>
    </div>
  </div>
{/if}

{#if convertModalFile}
  <div class="modal-overlay" onclick={() => { convertModalFile = null; convertError = null; }}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Convert format</h3>
      <p class="modal-hint">{convertModalFile.name}</p>
      <label class="convert-label">Target format:</label>
      <select
        bind:value={convertTargetFormat}
        class="convert-select"
        onchange={() => { if (convertAction === 'save') convertSavePath = getConvertSavePathDefault(); }}
      >
        {#each (convertFormats.writable || []).filter(e => e !== (convertModalFile.name.includes('.') ? '.' + convertModalFile.name.split('.').pop().toLowerCase() : '')) as ext}
          <option value={ext}>{ext}</option>
        {/each}
        {#if !(convertFormats.writable || []).length}
          <option value={convertTargetFormat}>{convertTargetFormat}</option>
        {/if}
      </select>
      <div class="convert-actions-row">
        <label>
          <input type="radio" name="convertAction" value="download" checked={convertAction === 'download'} onchange={() => { convertAction = 'download'; }} />
          Download converted file
        </label>
        <label>
          <input type="radio" name="convertAction" value="save" checked={convertAction === 'save'} onchange={() => { convertAction = 'save'; convertSavePath = getConvertSavePathDefault(); }} />
          Save to folder
        </label>
      </div>
      {#if convertAction === 'save'}
        <input 
          type="text" 
          class="convert-save-path"
          bind:value={convertSavePath} 
          placeholder="Path for saved file"
          onkeydown={(e) => e.key === 'Enter' && handleConvert()}
        />
      {/if}
      {#if convertError}
        <p class="convert-error">{convertError}</p>
      {/if}
      <div class="modal-actions convert-modal-actions">
        <button class="btn" onclick={() => { convertModalFile = null; convertError = null; }}>Cancel</button>
        <button class="btn btn-primary" onclick={handleConvert} disabled={convertLoading}>
          {convertLoading ? 'Converting…' : 'Convert'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if createFolderModal !== null}
  <div class="modal-overlay" onclick={() => { createFolderModal = null; newName = ''; }}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Create New Folder</h3>
      <p class="modal-hint">In: {createFolderModal || 'Root'}</p>
      <input 
        type="text" 
        bind:value={newName} 
        placeholder="Folder name"
        onkeydown={(e) => e.key === 'Enter' && handleCreateFolder()}
      />
      <div class="modal-actions">
        <button class="btn" onclick={() => { createFolderModal = null; newName = ''; }}>Cancel</button>
        <button class="btn btn-primary" onclick={handleCreateFolder}>Create</button>
      </div>
    </div>
  </div>
{/if}

{#if extractModal}
  <div class="modal-overlay" onclick={() => extractModal = null}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Extract ZIP File</h3>
      <p class="modal-hint">Extracting: {extractModal.split('/').pop()}</p>
      <label class="extract-label">Destination path:</label>
      <input 
        type="text" 
        bind:value={extractDestination} 
        placeholder="Destination path (leave empty for auto)"
        onkeydown={(e) => e.key === 'Enter' && handleExtract()}
      />
      {#if extractFolders.length > 0}
        <div class="folder-picker">
          <span class="folder-picker-label">Quick pick folder:</span>
          <div class="folder-picker-list">
            {#if $currentPath}
              <button class="folder-pick-btn" onclick={() => extractDestination = $currentPath}>
                📂 Current ({$currentPath.split('/').pop() || 'Root'})
              </button>
            {/if}
            {#each extractFolders as folder}
              <button class="folder-pick-btn" onclick={() => extractDestination = folder.path}>
                📁 {folder.name}
              </button>
            {/each}
          </div>
        </div>
      {/if}
      <div class="modal-actions">
        <button class="btn" onclick={() => extractModal = null}>Cancel</button>
        <button class="btn btn-primary" onclick={handleExtract}>Extract</button>
      </div>
    </div>
  </div>
{/if}

{#if previewModal && previewFile}
  <div class="preview-overlay" onclick={() => previewModal = null}>
    <div class="preview-modal" onclick={(e) => e.stopPropagation()}>
      <button class="preview-close" onclick={() => previewModal = null}>&times;</button>
      <h3 class="preview-title">{previewFile.name}</h3>
      <div class="preview-image-container">
        <img 
          src={getPreviewUrl(previewFile.path)} 
          alt={previewFile.name}
          class="preview-image"
          onerror={(e) => e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><rect fill="%23f0f0f0" width="600" height="600"/><text x="300" y="310" text-anchor="middle" fill="%23666" font-size="40">Unable to load preview</text></svg>'}
        />
      </div>
      <div class="preview-info">
        <span class="preview-type" style="color: {getFileTypeColor(previewFile.file_type)}">
          {previewFile.file_type}
        </span>
        <span class="preview-size">{formatFileSize(previewFile.size)}</span>
      </div>
      {#if isEmbroideryFileType(previewFile.file_type)}
        <div class="preview-colors">
          <span class="preview-colors-label">Colors:</span>
          {#if previewEmbroideryLoading}
            <span class="preview-colors-hint">Loading…</span>
          {:else if previewEmbroideryError}
            <span class="preview-colors-hint">{previewEmbroideryError}</span>
          {:else if previewEmbroideryInfo}
            <span class="preview-colors-count">
              {previewEmbroideryInfo.color_count} thread(s)
              {#if previewEmbroideryInfo.color_changes != null}
                · {previewEmbroideryInfo.color_changes} color change(s)
              {/if}
              {#if previewEmbroideryInfo.hoop_label}
                · Hoop: {previewEmbroideryInfo.hoop_label}
              {/if}
            </span>
            {#if previewEmbroideryInfo.color_count > 0}
              <div class="preview-swatches">
                {#each previewEmbroideryInfo.colors as color}
                  <span
                    class="color-swatch"
                    style="background-color: {color.hex};"
                    title={[color.catalog_number, color.description].filter(Boolean).join(' · ') || color.hex}
                  />
                {/each}
              </div>
            {/if}
          {/if}
        </div>
      {/if}
      {#if ($tags[previewFile.path] || []).length > 0}
        <div class="preview-tags">
          <span class="preview-tags-label">Tags:</span>
          {#each $tags[previewFile.path] || [] as tag}
            {@const src = ($tagSources[previewFile.path] || {})[tag]}
            <span class="file-tag-pill clickable" role="button" tabindex="0" title={src === 'auto' ? 'Auto-tagged · Click to show all' : 'Manual · Click to show all'} onclick={() => openTagView(tag)} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openTagView(tag); } }}>{tag}{#if src === 'auto'}<span class="tag-source-badge" aria-label="Auto-tagged">auto</span>{/if}</span>
          {/each}
        </div>
      {/if}
      <div class="preview-actions">
        <button class="btn" onclick={() => downloadFile(previewFile.path)}>⬇️ Download</button>
        {#if isEmbroideryFileType(previewFile.file_type)}
          <button class="btn" onclick={() => { previewModal = false; openConvertModal(previewFile); }}>🔄 Convert</button>
        {/if}
        <button class="btn" onclick={() => { previewModal = false; openRenameModal(previewFile); }}>✏️ Rename</button>
        <button class="btn" onclick={() => { previewModal = false; openMoveModal(previewFile); }}>📁 Move</button>
        <button class="btn" onclick={() => { previewModal = false; openTagModal(previewFile); }}>🏷️ Tags</button>
        <button class="btn btn-danger" onclick={async () => { 
          if (confirm(`Delete ${previewFile.name}?`)) {
            await deleteFiles([previewFile.path]);
            previewModal = false;
            fetchFiles($currentPath);
          }
        }}>🗑️ Delete</button>
      </div>
    </div>
  </div>
{/if}

{#if tagModal}
  <div class="modal-overlay" onclick={() => { tagModal = null; tagModalFile = null; suggestError = null; suggestedTags = []; }}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Manage Tags</h3>
      <div class="tag-list">
        {#each $tags[tagModal] || [] as tag}
          {@const src = ($tagSources[tagModal] || {})[tag]}
          <span class="tag">
            <span class="tag-name-with-source">{tag}{#if src === 'auto'}<span class="tag-source-badge" aria-label="Auto-tagged" title="Auto-tagged from image">auto</span>{/if}</span>
            <button class="tag-remove" onclick={() => handleRemoveTag(tag)}>&times;</button>
          </span>
        {/each}
      </div>
      <div class="tag-input-row">
        <input 
          type="text" 
          id="tagInput"
          placeholder="Add a tag..."
          onkeydown={(e) => {
            if (e.key === 'Enter') {
              handleAddTag(e.target.value);
              e.target.value = '';
            }
          }}
        />
        <button class="btn" onclick={(e) => {
          const input = document.getElementById('tagInput');
          handleAddTag(input.value);
          input.value = '';
        }}>Add</button>
      </div>
      {#if tagModalFile && !tagModalFile.is_directory && !tagModalFile.is_zip}
        <div class="suggest-from-image">
          <button 
            class="btn" 
            onclick={handleSuggestFromImage} 
            disabled={suggestLoading}
          >
            {suggestLoading ? '…' : 'Suggest from image'}
          </button>
          {#if suggestError}
            <p class="suggest-error">{suggestError}</p>
          {/if}
          {#if suggestedTags.length > 0}
            <div class="suggested-tags-row">
              <span class="available-tags-label">Suggested:</span>
              {#each suggestedTags as tag}
                <button class="tag-suggestion" onclick={() => handleAddSuggestedTag(tag)}>{tag}</button>
              {/each}
              <button class="btn btn-primary" onclick={handleAddAllSuggested}>Add all</button>
            </div>
          {/if}
        </div>
      {/if}
      {#if availableTags.length > 0}
        <div class="available-tags">
          <span class="available-tags-label">Suggestions:</span>
          {#each availableTags.filter(t => !($tags[tagModal] || []).includes(t)) as tag}
            <button class="tag-suggestion" onclick={() => handleAddTag(tag)}>{tag}</button>
          {/each}
        </div>
      {/if}
      <div class="modal-actions">
        <button class="btn" onclick={() => tagModal = null}>Close</button>
      </div>
    </div>
  </div>
{/if}

{#if autoTagResult !== null}
  <div class="modal-overlay" onclick={() => autoTagResult = null} role="dialog">
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Auto-tag complete</h3>
      <p class="modal-hint">
        Processed: {autoTagResult.processed} · Skipped (already tagged): {autoTagResult.skipped}
      </p>
      {#if autoTagResult.errors?.length > 0}
        <p class="suggest-error">Errors: {autoTagResult.errors.length}</p>
        <ul class="auto-tag-errors">
          {#each autoTagResult.errors.slice(0, 10) as err}
            <li>{typeof err === 'string' ? err : err}</li>
          {/each}
          {#if autoTagResult.errors.length > 10}
            <li>… and {autoTagResult.errors.length - 10} more</li>
          {/if}
        </ul>
      {/if}
      <div class="modal-actions">
        <button class="btn" onclick={() => autoTagResult = null}>Close</button>
      </div>
    </div>
  </div>
{/if}

{#if logoModal}
  <div class="modal-overlay" onclick={() => logoModal = null}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Set Folder Logo</h3>
      
      <div class="logo-upload-section">
        <p class="logo-hint">Upload an image file:</p>
        <input 
          type="file" 
          accept="image/*"
          bind:this={logoFileInput}
          onchange={handleLogoFileSelect}
        />
        {#if logoFile}
          <div class="logo-preview">
            <span class="logo-preview-label">Selected:</span>
            <img 
              src={URL.createObjectURL(logoFile)} 
              alt="Logo preview"
            />
          </div>
        {/if}
      </div>
      
      <div class="logo-url-section">
        <p class="logo-hint">Or enter a URL:</p>
        <input 
          type="text" 
          bind:value={logoUrl} 
          placeholder="https://example.com/logo.png"
          disabled={!!logoFile}
        />
      </div>
      
      {#if logoUrl && !logoFile}
        <div class="logo-preview">
          <span class="logo-preview-label">Preview:</span>
          <img 
            src={logoUrl} 
            alt="Logo preview"
            onerror={(e) => e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23ffcccc" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%23666" font-size="12">Invalid URL</text></svg>'}
          />
        </div>
      {/if}
      
      <div class="modal-actions">
        <button class="btn" onclick={() => { logoModal = null; logoUrl = ''; logoFile = null; }}>Cancel</button>
        <button class="btn btn-danger" onclick={async () => { await removeFolderLogo(logoModal); logoModal = null; logoUrl = ''; logoFile = null; await fetchFolderLogos(); }}>Remove Logo</button>
        <button class="btn btn-primary" onclick={handleSetLogo}>Save</button>
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
    flex-wrap: wrap;
  }

  .toolbar-left, .toolbar-right {
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
    transition: all 0.2s;
  }

  .btn:hover:not(:disabled) {
    background: var(--hover-bg);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn.active {
    background: var(--accent-bg);
    border-color: var(--accent-color);
  }

  .btn-danger {
    color: var(--danger-color);
    border-color: var(--danger-color);
  }

  .btn-danger:hover:not(:disabled) {
    background: var(--danger-bg);
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .btn-primary:hover {
    background: #1976d2;
  }

  .search {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    width: 200px;
    font-size: 14px;
    background: var(--input-bg);
    color: var(--text-primary);
  }

  .filter-select {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 14px;
    background: var(--input-bg);
    color: var(--text-primary);
    cursor: pointer;
  }

  .breadcrumb {
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    flex-wrap: wrap;
  }

  .breadcrumb-item {
    background: none;
    border: none;
    color: var(--accent-color);
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
  }

  .breadcrumb-item:hover {
    background: var(--accent-bg);
  }

  .breadcrumb-item.browsing {
    color: var(--accent-color);
    cursor: default;
  }

  .breadcrumb-sep {
    color: var(--text-secondary);
  }

  .breadcrumb-clear {
    margin-left: 12px;
    padding: 4px 10px;
    font-size: 13px;
  }

  .toolbar-secondary {
    padding: 8px 16px;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .select-all {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }

  .file-count {
    color: var(--text-secondary);
    font-size: 14px;
  }

  .loading {
    padding: 40px;
    text-align: center;
    color: var(--text-secondary);
  }

  .search-empty {
    padding: 48px 24px;
    text-align: center;
    color: var(--text-secondary);
  }

  .search-empty p {
    margin: 0 0 8px;
  }

  .search-empty-hint {
    font-size: 14px;
    max-width: 420px;
    margin-left: auto;
    margin-right: auto;
  }

  .error {
    padding: 12px 16px;
    background: var(--danger-bg);
    color: var(--danger-color);
    border-bottom: 1px solid var(--border-color);
  }

  .file-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 16px;
    padding: 16px;
  }

  .file-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
  }

  .file-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }

  .file-card.selected {
    border-color: var(--accent-color);
    background: var(--accent-bg);
  }

  .file-checkbox {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 20;
    padding: 8px;
    cursor: pointer;
    border-radius: 8px 0 4px 0;
    background: var(--bg-secondary);
    opacity: 0.85;
  }

  .file-checkbox:hover {
    opacity: 1;
    background: var(--accent-bg);
  }

  .file-thumb {
    width: 100%;
    height: 100px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-tertiary);
    border-radius: 4px;
    margin-bottom: 8px;
    overflow: hidden;
  }

  .file-thumb img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }

  .file-thumb .icon {
    font-size: 48px;
  }

  .file-name {
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 4px;
  }

  .file-info {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .file-type {
    font-weight: 500;
  }

  .file-actions {
    display: none;
    position: absolute;
    top: 0;
    right: 0;
    gap: 2px;
    z-index: 15;
    background: var(--bg-secondary);
    border-radius: 0 8px 0 4px;
    padding: 4px;
    opacity: 0.9;
  }

  .file-card:hover .file-actions {
    display: flex;
  }

  .file-actions button {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 2px 6px;
    cursor: pointer;
    font-size: 12px;
  }

  .file-actions button:hover {
    background: var(--hover-bg);
  }

  .file-actions button.action-delete:hover,
  .col-actions button.action-delete:hover {
    background: var(--danger-bg);
    border-color: var(--danger-color);
  }

  .extract-btn {
    width: 100%;
    margin-top: 8px;
    padding: 6px;
    background: #4caf50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
  }

  .extract-btn:hover {
    background: #43a047;
  }

  .file-list {
    flex: 1;
    background: var(--bg-secondary);
  }

  .list-header, .list-row {
    display: grid;
    grid-template-columns: 40px 1fr minmax(100px, 1.2fr) 100px 100px 120px;
    padding: 12px 16px;
    align-items: center;
  }

  .list-header {
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-color);
    font-weight: 500;
    color: var(--text-secondary);
    font-size: 14px;
  }

  .list-row {
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
  }

  .list-row:hover {
    background: var(--hover-bg);
  }

  .list-row.selected {
    background: var(--accent-bg);
  }

  .col-name {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .col-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
  }

  .list-path-hint {
    font-size: 11px;
    color: var(--text-secondary);
    margin-left: 4px;
  }

  .file-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin: 4px 0;
    min-height: 20px;
  }

  .file-tag-pill {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 10px;
    background: var(--accent-bg);
    color: var(--accent-color);
    max-width: 80px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .file-tag-pill.more {
    opacity: 0.8;
  }

  .file-tag-pill.clickable {
    cursor: pointer;
  }

  .file-tag-pill.clickable:hover {
    text-decoration: underline;
  }

  .tag-source-badge {
    font-size: 9px;
    margin-left: 3px;
    opacity: 0.85;
    text-transform: lowercase;
  }

  .file-path-hint {
    font-size: 10px;
    color: var(--text-secondary);
    margin-bottom: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .search-main { min-width: 220px; }
  .search-mode .btn { padding: 6px 10px; font-size: 13px; }
  .search-mode .btn.active { background: var(--accent-bg); border-color: var(--accent-color); }
  .semantic-label { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; white-space: nowrap; }
  .secondary-hint { font-size: 12px; color: var(--text-secondary); margin-right: auto; margin-left: 12px; }
  .preview-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-color); }
  .preview-tags-label { font-size: 13px; color: var(--text-secondary); margin-right: 4px; }
  .preview-colors { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-color); }
  .preview-colors-label { font-size: 13px; color: var(--text-secondary); margin-right: 4px; }
  .preview-colors-hint, .preview-colors-count { font-size: 13px; color: var(--text-secondary); }
  .preview-swatches { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
  .color-swatch { width: 18px; height: 18px; border-radius: 4px; border: 1px solid var(--border-color); flex-shrink: 0; }

  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
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

  .modal.modal-wide {
    min-width: 480px;
    max-height: 85vh;
    overflow: auto;
  }

  .modal h3 {
    margin: 0 0 16px;
  }

  .modal input {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 14px;
    box-sizing: border-box;
    background: var(--input-bg);
    color: var(--text-primary);
  }

  .modal-actions {
    margin-top: 16px;
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  .preview-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
  }

  .preview-modal {
    background: var(--bg-secondary);
    border-radius: 12px;
    padding: 24px;
    max-width: 90%;
    max-height: 90%;
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .preview-close {
    position: absolute;
    top: 12px;
    right: 12px;
    background: none;
    border: none;
    font-size: 32px;
    color: var(--text-secondary);
    cursor: pointer;
    line-height: 1;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .preview-close:hover {
    color: var(--text-primary);
  }

  .preview-title {
    margin: 0 0 16px;
    text-align: center;
    word-break: break-all;
    padding-right: 32px;
  }

  .preview-image-container {
    background: var(--bg-tertiary);
    border-radius: 8px;
    padding: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    max-width: 600px;
    max-height: 600px;
    overflow: hidden;
  }

  .preview-image {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }

  .preview-info {
    display: flex;
    gap: 24px;
    margin-top: 16px;
    font-size: 14px;
  }

  .preview-type {
    font-weight: 600;
  }

  .preview-size {
    color: var(--text-secondary);
  }

  .preview-actions {
    display: flex;
    gap: 8px;
    margin-top: 16px;
  }

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
  }

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: var(--accent-bg);
    color: var(--accent-color);
    border-radius: 12px;
    font-size: 12px;
  }

  .tag-name-with-source {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .tag-remove {
    background: none;
    border: none;
    color: var(--accent-color);
    cursor: pointer;
    padding: 0;
    font-size: 14px;
    line-height: 1;
  }

  .tag-input-row {
    display: flex;
    gap: 8px;
  }

  .tag-input-row input {
    flex: 1;
  }

  .available-tags {
    margin-top: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }

  .available-tags-label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .tag-suggestion {
    padding: 2px 8px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    font-size: 12px;
    cursor: pointer;
  }

  .tag-suggestion:hover {
    background: var(--hover-bg);
  }

  .suggest-from-image {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
  }

  .suggest-error {
    margin: 8px 0 0;
    font-size: 13px;
    color: var(--danger-color);
  }

  .suggested-tags-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-top: 8px;
  }

  .suggested-tags-row .available-tags-label {
    margin-right: 4px;
  }

  .auto-tag-errors {
    margin: 8px 0 0;
    padding-left: 20px;
    font-size: 12px;
    color: var(--danger-color);
    max-height: 120px;
    overflow-y: auto;
  }

  .folder-logo {
    width: 80px;
    height: 80px;
    object-fit: contain;
    border-radius: 4px;
  }

  .extract-label {
    display: block;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 4px;
  }

  .folder-picker {
    margin-top: 12px;
  }

  .folder-picker-label {
    font-size: 13px;
    color: var(--text-secondary);
  }

  .folder-picker-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
    max-height: 120px;
    overflow-y: auto;
  }

  .folder-pick-btn {
    padding: 4px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-tertiary);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 13px;
  }

  .folder-pick-btn:hover {
    background: var(--accent-bg);
    border-color: var(--accent-color);
  }

  .logo-hint {
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }

  .modal-hint {
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }

  .logo-preview {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .logo-preview-label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .logo-preview img {
    max-width: 100px;
    max-height: 100px;
    object-fit: contain;
    border-radius: 8px;
    border: 1px solid var(--border-color);
  }

  .convert-label,
  .convert-select {
    display: block;
    margin-bottom: 8px;
  }
  .convert-select {
    width: 100%;
    padding: 8px;
    font-size: 14px;
  }
  .convert-actions-row {
    margin: 12px 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .convert-actions-row label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }
  .convert-save-path {
    width: 100%;
    padding: 8px;
    margin-bottom: 8px;
    font-size: 14px;
  }
  .convert-error {
    color: var(--error-color, #c00);
    font-size: 13px;
    margin-bottom: 12px;
  }

  .convert-modal-actions {
    display: flex;
    flex-wrap: nowrap;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }
</style>
