import { expect, test } from '@playwright/test'

test('home loads hero and search', async ({ page }) => {
  await page.goto('/')
  await expect(
    page.getByRole('heading', { level: 1, name: /Stress-free insights/i }),
  ).toBeVisible()
  await expect(page.getByRole('search')).toBeVisible()
  await expect(page.getByLabel(/ticker/i)).toBeVisible()
})
