import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  THEME_STORAGE_KEY,
  applyColorModeToDocument,
  persistColorMode,
  readStoredColorMode,
} from './theme'

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  afterEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('readStoredColorMode defaults to light when unset', () => {
    expect(readStoredColorMode()).toBe('light')
  })

  it('readStoredColorMode reads persisted value', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    expect(readStoredColorMode()).toBe('dark')
    localStorage.setItem(THEME_STORAGE_KEY, 'light')
    expect(readStoredColorMode()).toBe('light')
  })

  it('readStoredColorMode ignores invalid values', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'nope')
    expect(readStoredColorMode()).toBe('light')
  })

  it('applyColorModeToDocument toggles html.dark', () => {
    applyColorModeToDocument('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    applyColorModeToDocument('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('persistColorMode writes THEME_STORAGE_KEY', () => {
    persistColorMode('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    persistColorMode('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })
})
