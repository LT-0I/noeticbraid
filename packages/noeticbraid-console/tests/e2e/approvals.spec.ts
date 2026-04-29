import { expect, test } from '@playwright/test'

test('approvals route renders the approval queue', async ({ page }) => {
  await page.goto('/approvals')
  await expect(page.getByTestId('approvals-root')).toBeVisible()
  await expect(page.getByTestId('approval-item-approval_stage1_candidate_001')).toBeVisible()
})
