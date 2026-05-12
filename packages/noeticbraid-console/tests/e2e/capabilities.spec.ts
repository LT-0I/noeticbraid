import { expect, test } from '@playwright/test'

test('capabilities route lists first four endpoints and runs mock health-check', async ({ page }) => {
  await page.goto('/capabilities')

  await expect(page.getByTestId('capabilities-root')).toBeVisible()
  await expect(page.getByTestId('capability-cap_claude_code_cli')).toContainText('Claude Code CLI')
  await expect(page.getByTestId('capability-cap_codex_cli')).toContainText('Codex CLI')
  await expect(page.getByTestId('capability-cap_gemini_cli')).toContainText('Gemini CLI')
  await expect(page.getByTestId('capability-cap_gemini_web')).toContainText('Gemini Web')
  await page.getByTestId('health-check-cap_codex_cli').click()
  await expect(page.getByTestId('health-check-result')).toContainText('mock')
})
