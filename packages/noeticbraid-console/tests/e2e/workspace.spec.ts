import { expect, test } from '@playwright/test'

test('workspace route renders threads from the Phase 1.1 contract mock', async ({ page }) => {
  await page.goto('/workspace')
  await expect(page.getByTestId('workspace-root')).toBeVisible()
  await expect(page.getByTestId('thread-item-task_stage1_candidate_001')).toBeVisible()
})
