import { expect, test } from '@playwright/test'

test('theme toggle adds and removes dark class on html', async ({ page }) => {
  await page.goto('/')
  expect(
    await page.evaluate(() => document.documentElement.classList.contains('dark')),
  ).toBe(false)

  await page.getByRole('button', { name: /switch to dark mode/i }).click()
  expect(
    await page.evaluate(() => document.documentElement.classList.contains('dark')),
  ).toBe(true)

  await page.getByRole('button', { name: /switch to light mode/i }).click()
  expect(
    await page.evaluate(() => document.documentElement.classList.contains('dark')),
  ).toBe(false)
})
