import { writable, derived, get } from 'svelte/store';

const API_URL = (typeof import.meta.env.VITE_API_URL === 'string' && import.meta.env.VITE_API_URL) || '';

function createThemeStore() {
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('theme') : null;
  const prefersDark = typeof window !== 'undefined' ? window.matchMedia('(prefers-color-scheme: dark)').matches : true;
  const initial = stored || (prefersDark ? 'dark' : 'light');
  
  const { subscribe, set, update } = writable(initial);
  
  return {
    subscribe,
    set: (value) => {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('theme', value);
      }
      set(value);
    },
    toggle: () => {
      update(current => {
        const newTheme = current === 'dark' ? 'light' : 'dark';
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('theme', newTheme);
        }
        return newTheme;
      });
    }
  };
}

export const theme = createThemeStore();

function createPathStore() {
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('currentPath') : '';
  const { subscribe, set } = writable(stored || '');
  
  return {
    subscribe,
    set: (value) => {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('currentPath', value);
      }
      set(value);
    },
    get: () => {
      if (typeof localStorage !== 'undefined') {
        return localStorage.getItem('currentPath') || '';
      }
      return '';
    }
  };
}

export const currentPath = createPathStore();
export const files = writable([]);
export const selectedFiles = writable(new Set());
export const loading = writable(false);
export const error = writable(null);
export const viewMode = writable('grid');

export async function fetchFiles(path = '') {
  loading.set(true);
  error.set(null);
  
  try {
    const response = await fetch(`${API_URL}/api/files?path=${encodeURIComponent(path)}`);
    if (!response.ok) throw new Error('Failed to fetch files');
    
    const data = await response.json();
    files.set(data.items);
    currentPath.set(data.path);
    selectedFiles.set(new Set());
    if (data.items?.length) {
      const paths = data.items.map(i => i.path);
      const batch = await fetchTagsBatch(paths);
      tags.update(t => ({ ...t, ...batch.tags }));
    }
  } catch (e) {
    error.set(e.message);
  } finally {
    loading.set(false);
  }
}

export async function deleteFiles(paths) {
  loading.set(true);
  error.set(null);
  
  try {
    const response = await fetch(`${API_URL}/api/files`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: paths })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.error || 'Failed to delete');
    if (data.success === false && data.errors?.length) throw new Error(data.errors.join('; '));
    return data;
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

export async function createFolder(path) {
  loading.set(true);
  error.set(null);
  
  try {
    const response = await fetch(`${API_URL}/api/files/folder?path=${encodeURIComponent(path)}`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error('Failed to create folder');
    
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

export async function moveFile(source, destination) {
  loading.set(true);
  error.set(null);
  
  try {
    const response = await fetch(`${API_URL}/api/files/${encodeURIComponent(source)}/move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination })
    });
    if (!response.ok) throw new Error('Failed to move file');
    
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

export async function renameFile(path, newName) {
  loading.set(true);
  error.set(null);
  
  try {
    const response = await fetch(`${API_URL}/api/files/${encodeURIComponent(path)}?new_name=${encodeURIComponent(newName)}`, {
      method: 'PUT'
    });
    if (!response.ok) throw new Error('Failed to rename file');
    
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

export async function extractZip(path, destination = '') {
  loading.set(true);
  error.set(null);
  
  try {
    const response = await fetch(`${API_URL}/api/files/${encodeURIComponent(path)}/extract?destination=${encodeURIComponent(destination)}`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error('Failed to extract zip');
    
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

export async function uploadFile(path, file) {
  loading.set(true);
  error.set(null);
  
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_URL}/api/files?path=${encodeURIComponent(path)}`, {
      method: 'POST',
      body: formData
    });
    if (!response.ok) throw new Error('Failed to upload file');
    
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

export async function getZipContents(path) {
  loading.set(true);
  error.set(null);
  
  try {
    const response = await fetch(`${API_URL}/api/files/${encodeURIComponent(path)}/contents`);
    if (!response.ok) throw new Error('Failed to get zip contents');
    
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

export async function getFilesInfo(paths) {
  if (!paths?.length) return { items: [] };
  try {
    const response = await fetch(`${API_URL}/api/files/info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    });
    if (!response.ok) throw new Error('Failed to get file info');
    const data = await response.json();
    return { items: data.items || [] };
  } catch (e) {
    return { items: [] };
  }
}

export function getThumbnailUrl(path) {
  return `${API_URL}/api/thumbnails/${encodeURIComponent(path)}`;
}

export function getPreviewUrl(path) {
  return `${API_URL}/api/thumbnails/preview/${encodeURIComponent(path)}`;
}

export function getDownloadUrl(path) {
  return `${API_URL}/api/files/${encodeURIComponent(path)}/download`;
}

export async function getConvertFormats() {
  const response = await fetch(`${API_URL}/api/files/convert/formats`);
  if (!response.ok) throw new Error('Failed to load convert formats');
  return response.json();
}

export async function convertFile(sourcePath, targetFormat, destinationPath = null) {
  const ext = (targetFormat || '').trim().toLowerCase();
  const fmt = ext.startsWith('.') ? ext : `.${ext}`;
  const body = { source_path: sourcePath, target_format: fmt, destination_path: destinationPath || undefined };
  const response = await fetch(`${API_URL}/api/files/convert`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || response.statusText || 'Conversion failed');
  }
  if (destinationPath) {
    return response.json();
  }
  const blob = await response.blob();
  const name = response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)"?/)?.[1] || sourcePath.replace(/\.[^.]+$/, '') + fmt;
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
  return { path: null, size: blob.size };
}

export async function downloadFile(path) {
  try {
    const response = await fetch(`${API_URL}/api/files/${encodeURIComponent(path)}/download`);
    if (!response.ok) throw new Error('Failed to download file');
    
    const blob = await response.blob();
    const filename = path.split('/').pop();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (e) {
    error.set(e.message);
    throw e;
  }
}

export async function downloadFiles(paths) {
  for (const path of paths) {
    await downloadFile(path);
  }
}

export function getFileTypeColor(fileType) {
  const colors = {
    'Tajima': '#4a90d9',
    'Brother': '#7b68ee',
    'Melco': '#50c878',
    'Viking': '#f4a460',
    'Janome': '#ff6b6b',
    'Wilcom': '#ffd700',
    'Unknown': '#888'
  };
  return colors[fileType] || colors['Unknown'];
}

export function formatFileSize(bytes) {
  if (!bytes) return '-';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

export const tags = writable({});
/** path -> { tagName: "auto" | "manual" } for badge/tooltip */
export const tagSources = writable({});

export async function fetchTags(path) {
  try {
    const response = await fetch(`${API_URL}/api/tags?path=${encodeURIComponent(path)}`);
    if (!response.ok) throw new Error('Failed to fetch tags');
    const data = await response.json();
    tags.update(t => ({ ...t, [path]: data.tags || [] }));
    tagSources.update(s => ({ ...s, [path]: data.tag_sources || {} }));
    return data.tags || [];
  } catch (e) {
    return [];
  }
}

export async function setTags(path, tagList) {
  try {
    const response = await fetch(`${API_URL}/api/tags?path=${encodeURIComponent(path)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tags: tagList })
    });
    if (!response.ok) throw new Error('Failed to set tags');
    const data = await response.json();
    tags.update(t => ({ ...t, [path]: data.tags || tagList }));
    tagSources.update(s => ({ ...s, [path]: data.tag_sources || {} }));
    return data;
  } catch (e) {
    error.set(e.message);
    throw e;
  }
}

export async function removeTags(path) {
  try {
    const response = await fetch(`${API_URL}/api/tags?path=${encodeURIComponent(path)}`, {
      method: 'DELETE'
    });
    if (!response.ok) throw new Error('Failed to remove tags');
    tags.update(t => {
      const newTags = { ...t };
      delete newTags[path];
      return newTags;
    });
    tagSources.update(s => {
      const next = { ...s };
      delete next[path];
      return next;
    });
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  }
}

export async function searchByTag(tag) {
  try {
    const response = await fetch(`${API_URL}/api/tags/search?tag=${encodeURIComponent(tag)}`);
    if (!response.ok) throw new Error('Failed to search by tag');
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  }
}

export async function getAllTags() {
  try {
    const response = await fetch(`${API_URL}/api/tags/all`);
    if (!response.ok) throw new Error('Failed to get all tags');
    return await response.json();
  } catch (e) {
    return { tags: [] };
  }
}

export async function getAllTagsWithCounts() {
  try {
    const response = await fetch(`${API_URL}/api/tags/all?counts=1`);
    if (!response.ok) throw new Error('Failed to get tags with counts');
    const data = await response.json();
    return { tags: data.tags || [] };
  } catch (e) {
    return { tags: [] };
  }
}

export async function getPathsWithTags() {
  try {
    const response = await fetch(`${API_URL}/api/tags/paths`);
    if (!response.ok) throw new Error('Failed to get paths');
    const data = await response.json();
    return { paths: data.paths || [] };
  } catch (e) {
    return { paths: [] };
  }
}

export async function mergeTags(source, target) {
  const response = await fetch(`${API_URL}/api/tags/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, target })
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || response.statusText || 'Merge failed');
  }
  return await response.json();
}

export async function deleteTagGlobally(tag) {
  const response = await fetch(`${API_URL}/api/tags/globally?tag=${encodeURIComponent(tag)}`, {
    method: 'DELETE'
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || response.statusText || 'Delete failed');
  }
  return await response.json();
}

export async function bulkAddTag(tag, paths) {
  const response = await fetch(`${API_URL}/api/tags/bulk-add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag, paths })
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || response.statusText || 'Bulk add failed');
  }
  return await response.json();
}

export async function suggestTags(path) {
  const response = await fetch(`${API_URL}/api/tags/suggest?path=${encodeURIComponent(path)}`, {
    method: 'POST'
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || response.statusText || 'Suggestions unavailable');
  }
  return await response.json();
}

export async function runAutoTag(path = '') {
  const params = path ? `?path=${encodeURIComponent(path)}` : '';
  const response = await fetch(`${API_URL}/api/tags/run-auto-tag${params}`, { method: 'POST' });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || response.statusText || 'Auto-tag failed');
  }
  return await response.json();
}

export async function fetchTagsBatch(paths) {
  if (!paths?.length) return { tags: {}, tag_sources: {} };
  try {
    const response = await fetch(`${API_URL}/api/tags/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    });
    if (!response.ok) return { tags: {}, tag_sources: {} };
    const data = await response.json();
    if (data.tags && Object.keys(data.tags).length) {
      tags.update(t => ({ ...t, ...data.tags }));
    }
    if (data.tag_sources && Object.keys(data.tag_sources).length) {
      tagSources.update(s => ({ ...s, ...data.tag_sources }));
    }
    return { tags: data.tags || {}, tag_sources: data.tag_sources || {} };
  } catch (e) {
    return { tags: {}, tag_sources: {} };
  }
}

export async function searchAllFiles(q, root = '', semantic = false, limit = 500) {
  loading.set(true);
  error.set(null);
  try {
    const params = new URLSearchParams({ q: q || '', root: root || '', limit: String(limit) });
    if (semantic) params.set('semantic', 'true');
    const response = await fetch(`${API_URL}/api/files/search?${params}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const msg = data.detail || data.error || (typeof data === 'string' ? data : 'Search failed');
      throw new Error(Array.isArray(msg) ? msg.join(' ') : msg);
    }
    if (data.error) {
      error.set(data.error);
    }
    if (data.items?.length) {
      const batch = await fetchTagsBatch(data.items.map(i => i.path));
      tags.update(t => ({ ...t, ...batch.tags }));
    }
    return { path: data.path, items: data.items || [], total: data.total ?? 0 };
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

/** Search current folder and below first, then everywhere else. Always uses fuzzy. Results sorted by relevance (best match first). */
export async function searchCurrentThenEverywhere(q, currentPath = '', limit = 500) {
  loading.set(true);
  error.set(null);
  try {
    const currentRoot = (currentPath || '').trim();
    const [currentRes, everywhereRes] = await Promise.all([
      fetch(`${API_URL}/api/files/search?${new URLSearchParams({ q: q || '', root: currentRoot, semantic: 'true', limit: String(limit) })}`).then(r => r.json().catch(() => ({}))),
      fetch(`${API_URL}/api/files/search?${new URLSearchParams({ q: q || '', root: '', semantic: 'true', limit: String(limit * 2) })}`).then(r => r.json().catch(() => ({})))
    ]);
    const currentItems = currentRes.items || [];
    const currentPaths = new Set(currentItems.map(i => i.path));
    const everywhereItems = (everywhereRes.items || []).filter(i => !currentPaths.has(i.path));
    const merged = [...currentItems, ...everywhereItems];
    if (merged.length) {
      const batch = await fetchTagsBatch(merged.map(i => i.path));
      tags.update(t => ({ ...t, ...batch.tags }));
    }
    return { path: currentRoot, items: merged, total: merged.length };
  } catch (e) {
    error.set(e.message);
    throw e;
  } finally {
    loading.set(false);
  }
}

export const folderLogos = writable({});

export async function fetchFolderLogos() {
  try {
    const response = await fetch(`${API_URL}/api/logos`);
    if (!response.ok) throw new Error('Failed to fetch logos');
    const data = await response.json();
    const resolved = {};
    for (const [path, url] of Object.entries(data)) {
      resolved[path] = url.startsWith('/') ? `${API_URL}${url}` : url;
    }
    folderLogos.set(resolved);
    return resolved;
  } catch (e) {
    return {};
  }
}

export async function setFolderLogo(path, logoUrl) {
  try {
    const response = await fetch(`${API_URL}/api/logos/${encodeURIComponent(path)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ logo_url: logoUrl })
    });
    if (!response.ok) throw new Error('Failed to set logo');
    folderLogos.update(logos => ({ ...logos, [path]: logoUrl }));
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  }
}

export async function uploadFolderLogo(path, file) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_URL}/api/logos/${encodeURIComponent(path)}/upload`, {
      method: 'POST',
      body: formData
    });
    if (!response.ok) throw new Error('Failed to upload logo');
    const data = await response.json();
    const resolvedUrl = data.logo_url.startsWith('/') ? `${API_URL}${data.logo_url}` : data.logo_url;
    folderLogos.update(logos => ({ ...logos, [path]: resolvedUrl }));
    return data;
  } catch (e) {
    error.set(e.message);
    throw e;
  }
}

export async function removeFolderLogo(path) {
  try {
    const response = await fetch(`${API_URL}/api/logos/${encodeURIComponent(path)}`, {
      method: 'DELETE'
    });
    if (!response.ok) throw new Error('Failed to remove logo');
    folderLogos.update(logos => {
      const newLogos = { ...logos };
      delete newLogos[path];
      return newLogos;
    });
    return await response.json();
  } catch (e) {
    error.set(e.message);
    throw e;
  }
}
