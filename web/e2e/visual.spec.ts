import { expect, test } from '@playwright/test'

test.describe('visual regression', () => {
  test.skip(
    ({ browserName, isMobile }) => browserName !== 'chromium' || isMobile || !!process.env.CI,
    'visual baselines use the local export and desktop chromium',
  )

  test('home light', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    await page.goto('/')
    await page.locator('.event-item').first().waitFor()
    await page.waitForTimeout(400)
    await expect(page).toHaveScreenshot('home-light.png', {
      fullPage: true,
      animations: 'disabled',
      maxDiffPixelRatio: 0.02,
    })
  })

  test('home dark', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.goto('/')
    await page.locator('.event-item').first().waitFor()
    await page.waitForTimeout(400)
    await expect(page).toHaveScreenshot('home-dark.png', {
      fullPage: true,
      animations: 'disabled',
      maxDiffPixelRatio: 0.02,
    })
  })

  test('methods light', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    await page.goto('/methods')
    await page.getByRole('heading', { name: 'Methods' }).waitFor()
    await expect(page).toHaveScreenshot('methods-light.png', {
      fullPage: true,
      animations: 'disabled',
      maxDiffPixelRatio: 0.02,
    })
  })
})
