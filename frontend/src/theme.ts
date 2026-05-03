export const THEME_STORAGE_KEY = 'tranquilytics-theme'

export type ColorMode = 'light' | 'dark'

export function readStoredColorMode(): ColorMode {
  if (typeof window === 'undefined') return 'light'
  try {
    const v = localStorage.getItem(THEME_STORAGE_KEY)
    if (v === 'dark' || v === 'light') return v
  } catch {
    /* ignore */
  }
  return 'light'
}

export function persistColorMode(mode: ColorMode): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    /* ignore */
  }
}

export function applyColorModeToDocument(mode: ColorMode): void {
  document.documentElement.classList.toggle('dark', mode === 'dark')
}
