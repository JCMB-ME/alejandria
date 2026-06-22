/**
 * Authentication store + theme store.
 */

import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import type { User } from '$api/types';
import { auth as authApi } from '$api/client';

export interface CustomTheme {
  id: string;
  name: string;
  base: 'light' | 'dark';
  colors: {
    bg: string;
    surface: string;
    border: string;
    text: string;
    accent: string;
  };
}

export const user = writable<User | null>(null);
export const theme = writable<string>('light');
export const readerTheme = writable<'light' | 'sepia' | 'dark'>('light');
export const sidebarOpen = writable(false);
export const customThemes = writable<CustomTheme[]>([]);

let customThemesList: CustomTheme[] = [];
customThemes.subscribe(val => {
  customThemesList = val;
});

export async function loadUser(): Promise<User | null> {
  if (!browser) return null;
  try {
    const u = await authApi.me();
    setUser(u);
    return u;
  } catch {
    setUser(null);
    return null;
  }
}

export function setUser(u: User | null) {
  user.set(u);
  if (u) {
    if (browser) {
      const savedReaderTheme = localStorage.getItem('alejandria-reader-theme');
      if (savedReaderTheme) {
        readerTheme.set(savedReaderTheme as any);
        return;
      }
    }
    
    // Fallback: if user reader_theme is light (default) but the app is in dark mode, match it.
    const appTheme = browser ? (localStorage.getItem('alejandria-theme') || 'light') : 'light';
    const dbTheme = u.reader_theme as 'light' | 'sepia' | 'dark';
    
    if (dbTheme === 'light' && (appTheme === 'dark' || appTheme === 'sepia')) {
      readerTheme.set(appTheme);
    } else {
      readerTheme.set(dbTheme || 'light');
    }
  }
}

export function clearUser() {
  user.set(null);
}

export function applyTheme(t: string) {
  theme.set(t);
  if (!browser) return;
  localStorage.setItem('alejandria-theme', t);
  
  const root = document.documentElement;
  
  // Reset custom style overrides first
  root.style.removeProperty('--bg');
  root.style.removeProperty('--surface');
  root.style.removeProperty('--elevated');
  root.style.removeProperty('--border');
  root.style.removeProperty('--text');
  root.style.removeProperty('--text-muted');
  root.style.removeProperty('--text-soft');
  root.style.removeProperty('--accent');
  root.style.removeProperty('--accent-hover');
  root.style.removeProperty('--link');
  
  if (t === 'light' || t === 'dark' || t === 'sepia') {
    root.setAttribute('data-theme', t);
    root.classList.toggle('dark', t === 'dark');
  } else {
    // Custom theme! Find it
    const found = customThemesList.find(ct => ct.id === t);
    if (found) {
      root.setAttribute('data-theme', found.base);
      root.classList.toggle('dark', found.base === 'dark');
      
      root.style.setProperty('--bg', found.colors.bg);
      root.style.setProperty('--surface', found.colors.surface);
      root.style.setProperty('--border', found.colors.border);
      root.style.setProperty('--text', found.colors.text);
      root.style.setProperty('--accent', found.colors.accent);
      
      // Compute variables dynamically using CSS color-mix
      root.style.setProperty('--elevated', 'color-mix(in srgb, var(--surface) 92%, var(--text) 8%)');
      root.style.setProperty('--text-muted', 'color-mix(in srgb, var(--text) 70%, var(--bg) 30%)');
      root.style.setProperty('--text-soft', 'color-mix(in srgb, var(--text) 50%, var(--bg) 50%)');
      root.style.setProperty('--accent-hover', 'color-mix(in srgb, var(--accent) 85%, var(--text) 15%)');
      root.style.setProperty('--link', 'var(--accent)');
    } else {
      root.setAttribute('data-theme', 'light');
      root.classList.remove('dark');
    }
  }
}

export function setTheme(t: string) {
  applyTheme(t);
}

export function setReaderTheme(t: 'light' | 'sepia' | 'dark') {
  readerTheme.set(t);
  if (browser) {
    localStorage.setItem('alejandria-reader-theme', t);
  }
}

export function saveCustomTheme(ct: CustomTheme) {
  customThemes.update(list => {
    const idx = list.findIndex(item => item.id === ct.id);
    if (idx >= 0) {
      list[idx] = ct;
    } else {
      list.push(ct);
    }
    if (browser) {
      localStorage.setItem('alejandria-custom-themes', JSON.stringify(list));
    }
    return list;
  });
  
  const active = localStorage.getItem('alejandria-theme');
  if (active === ct.id) {
    applyTheme(ct.id);
  }
}

export function deleteCustomTheme(id: string) {
  customThemes.update(list => {
    const updated = list.filter(item => item.id !== id);
    if (browser) {
      localStorage.setItem('alejandria-custom-themes', JSON.stringify(updated));
    }
    return updated;
  });
  
  const active = localStorage.getItem('alejandria-theme');
  if (active === id) {
    applyTheme('light');
  }
}

export function initTheme() {
  if (!browser) return;
  
  const savedCustoms = localStorage.getItem('alejandria-custom-themes');
  if (savedCustoms) {
    try {
      customThemes.set(JSON.parse(savedCustoms));
    } catch {}
  }
  
  const saved = localStorage.getItem('alejandria-theme') || 'light';
  applyTheme(saved);

  // Check localStorage for reader theme first, then fallback to matching app theme
  const savedReaderTheme = localStorage.getItem('alejandria-reader-theme');
  if (savedReaderTheme) {
    readerTheme.set(savedReaderTheme as any);
  } else {
    if (saved === 'dark' || saved === 'sepia') {
      readerTheme.set(saved);
    } else if (saved === 'light') {
      readerTheme.set('light');
    } else {
      // Custom theme - check its base
      try {
        const customList = JSON.parse(savedCustoms || '[]');
        const found = customList.find((ct: any) => ct.id === saved);
        if (found && (found.base === 'dark' || found.base === 'light')) {
          readerTheme.set(found.base);
        }
      } catch {}
    }
  }

  // Listen to system theme changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('alejandria-theme')) {
      const sysTheme = e.matches ? 'dark' : 'light';
      applyTheme(sysTheme);
      readerTheme.set(sysTheme as any);
      localStorage.removeItem('alejandria-reader-theme'); // Clear reader-specific theme to follow system
    }
  });
}
