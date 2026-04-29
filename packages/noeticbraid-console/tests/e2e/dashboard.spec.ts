import { expect, test } from '@playwright/test'

test('dashboard route renders with health badge showing contract 1.0.0', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('dashboard-root')).toBeVisible()
  await expect(page.getByTestId('health-badge')).toContainText('1.0.0')
  await expect(page.getByTestId('empty-state')).toBeVisible()
})
