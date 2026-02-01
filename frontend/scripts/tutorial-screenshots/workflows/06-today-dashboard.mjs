/**
 * Workflow 06 – Today Dashboard
 *
 * Captures the Today tab overview including onboarding progress,
 * metric cards, Sous Chef widget, and break mode toggle.
 */

export const meta = { name: 'Today Dashboard', dir: '06_today_dashboard' }

export default async function capture(ctx) {
  const { chefPage, screenshot, openChefTab, settle } = ctx

  // 1. Navigate to Today tab and screenshot the full dashboard overview
  await openChefTab(chefPage, 'Today')
  await chefPage.locator('.today-dashboard').waitFor({ state: 'visible', timeout: 10000 }).catch(() => {})
  await settle(chefPage)
  await screenshot(chefPage, 'today-dashboard-overview')

  // 2. Screenshot metric cards if visible (they live on the insights/legacy dashboard area,
  //    but the Today dashboard has its own cards like "Needs Attention" action cards)
  const metricCards = chefPage.locator('.chef-metric-card')
  const metricCardCount = await metricCards.count().catch(() => 0)
  if (metricCardCount > 0) {
    await metricCards.first().scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage, 400)
    await screenshot(chefPage, 'metric-cards')
  }

  // Also capture the today-cards section (urgent action items) if present
  const todayCards = chefPage.locator('.today-cards')
  if (await todayCards.count().catch(() => 0)) {
    await todayCards.first().scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage, 400)
    await screenshot(chefPage, 'today-action-cards')
  }

  // 3. Screenshot onboarding checklist if still visible (shows progress)
  const checklist = chefPage.locator('.onboarding-checklist, .onboarding-collapsed, .onboarding-complete')
  if (await checklist.count().catch(() => 0)) {
    await checklist.first().scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage, 400)
    await screenshot(chefPage, 'onboarding-checklist-progress')
  }

  // 4. Look for Sous Chef widget launcher button and screenshot
  const sousChefLauncher = chefPage.locator('.sc-launcher').first()
  if (await sousChefLauncher.isVisible().catch(() => false)) {
    await sousChefLauncher.scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage, 400)
    await screenshot(chefPage, 'sous-chef-widget-available')
  }

  // 5. Screenshot the break mode toggle area if visible
  const breakSection = chefPage.locator('.today-break-section, .today-break-card')
  if (await breakSection.count().catch(() => 0)) {
    await breakSection.first().scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage, 400)
    await screenshot(chefPage, 'break-mode-toggle')
  }
}
