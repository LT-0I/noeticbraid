import { expect, test } from '@playwright/test'

test('OMC ingestion workspace shows task card candidates and explicit adoption', async ({ page }) => {
  await page.goto('/projects/omc-ingest')

  await expect(page.getByTestId('omc-project-root')).toBeVisible()
  await expect(page.getByRole('heading', { name: '吸收 OMC' })).toBeVisible()
  await expect(page.getByTestId('omc-task-card')).toBeVisible()
  await expect(page.getByTestId('external-reference-pool')).toContainText('OMC_DEBATE_LOOP.md')
  await expect(page.getByTestId('candidate-item-memory_omc_ingest_debate_loop')).toBeVisible()
  await page.getByTestId('adopt-memory_omc_ingest_debate_loop').click()
  await expect(page.getByTestId('adopted-memory_omc_ingest_debate_loop')).toBeVisible()
})
