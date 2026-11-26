import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.describe('public pages', () => {
  test('home shows the latest day, ranked list and bubbles', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toContainText('biggest pageview jumps')
    await expect(page.getByRole('region', { name: /Events on/ })).toBeVisible()
    await expect(page.locator('.event-item').first()).toBeVisible()
    await expect(page.locator('.bubble-svg')).toBeVisible()
    await expect(page.locator('.event-item').first().getByRole('link')).toHaveAttribute(
      'href',
      /^\/e\//,
    )
  })

  test('event, article and day pages link to each other', async ({ page }) => {
    await page.goto('/')
    await page.locator('.event-item').first().getByRole('link').click()
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByText('Text from')).toBeVisible()
    await page.getByRole('link', { name: 'View history' }).first().click()
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.locator('svg.chart')).toBeVisible()
    await expect(page.getByText('Spike days')).toBeVisible()
  })

  test('search finds an indexed article', async ({ page }) => {
    await page.goto('/search?q=moon')
    await expect(page.getByRole('heading', { name: 'Search articles' })).toBeVisible()
    await expect(page.getByRole('link', { name: /Moon/i }).first()).toBeVisible()
  })

  test('methods page states the detector and limitations', async ({ page }) => {
    await page.goto('/methods')
    await expect(page.getByRole('heading', { name: 'Methods' })).toBeVisible()
    await expect(page.getByText('robust z-score')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Limitations' })).toBeVisible()
  })

  test('missing day and unknown routes are explained', async ({ page }) => {
    await page.goto('/d/1999-01-01')
    await expect(page.getByText('No data file for 1 January 1999')).toBeVisible()
    await page.goto('/this/does/not/exist')
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  })

  test('theme choice persists across reloads', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Switch to (dark|light) theme/ }).click()
    const theme = await page.locator('html').getAttribute('data-theme')
    expect(theme === 'dark' || theme === 'light').toBe(true)
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme ?? '')
  })

  test('data failure shows a retry state', async ({ page }) => {
    await page.route('**/data/manifest.json', (route) => route.abort())
    await page.goto('/')
    await expect(page.getByText('Could not load this page')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
  })

  test('home page has no serious axe violations', async ({ page }) => {
    await page.goto('/')
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    expect(
      results.violations.filter(
        (violation) => violation.impact === 'serious' || violation.impact === 'critical',
      ),
    ).toEqual([])
  })

  test('privacy page makes the storage promise', async ({ page }) => {
    await page.goto('/privacy')
    await expect(page.getByText('No cookies.')).toBeVisible()
    await expect(page.getByText('no stored user input', { exact: false })).toBeVisible()
  })
})

test.describe('keyboard and motion', () => {
  test('keyboard focus reaches the skip link', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Skip to content' }).focus()
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/#main-content$/)
  })

  test('reduced motion still renders the day', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/')
    await expect(page.locator('.event-item').first()).toBeVisible()
  })
})
