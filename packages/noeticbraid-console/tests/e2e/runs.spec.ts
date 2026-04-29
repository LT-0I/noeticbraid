import { expect, test } from '@playwright/test'

test('runs route renders the run ledger timeline', async ({ page }) => {
  await page.goto('/runs')
  await expect(page.getByTestId('runs-root')).toBeVisible()
  await expect(page.getByTestId('run-item-run_stage1_candidate_001')).toBeVisible()
})
