/**
 * Workflow 12 – Insights & Analytics
 *
 * Captures the chef insights/analytics dashboard including:
 * - Full insights dashboard view
 * - Summary metric cards (revenue overview)
 * - Time-range selector interaction
 * - Trend charts (revenue, orders, clients)
 * - Order breakdown pie chart area
 * - Analytics drawer opened from a metric card
 * - Final full-page overview
 */

export const meta = { name: 'Insights & Analytics', dir: '12_insights' }

export default async function capture(ctx) {
  const { chefPage, baseUrl, screenshot, openChefTab, settle } = ctx

  // ── 1. Navigate to Insights tab and screenshot the full dashboard ──
  await openChefTab(chefPage, 'Insights')
  await chefPage.getByRole('heading', { name: 'Insights' }).waitFor({ timeout: 15000 }).catch(() => {})
  await chefPage.waitForLoadState('networkidle').catch(() => {})
  await settle(chefPage, 800)
  await screenshot(chefPage, 'insights-dashboard-full')

  // ── 2. Screenshot the revenue overview metric cards ──
  try {
    const metricGrid = chefPage.locator('.insights-metric-grid').first()
    await metricGrid.waitFor({ state: 'visible', timeout: 8000 })
    await metricGrid.scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage)
    await screenshot(chefPage, 'insights-revenue-metric-cards')
  } catch {
    // Fallback: try the Today dashboard metric cards
    try {
      const metricCards = chefPage.locator('.chef-metric-card').first()
      await metricCards.waitFor({ state: 'visible', timeout: 5000 })
      await screenshot(chefPage, 'insights-metric-cards-fallback')
    } catch {
      // No metric cards available
    }
  }

  // ── 3. Click the 30d time-range button and screenshot ──
  try {
    const rangeSelector = chefPage.locator('.insights-range-selector').first()
    await rangeSelector.waitFor({ state: 'visible', timeout: 5000 })

    const btn30d = rangeSelector.locator('.range-btn', { hasText: '30d' })
    if (await btn30d.count()) {
      await btn30d.click()
      await settle(chefPage, 800)
      await screenshot(chefPage, 'insights-30d-range-selected')
    }
  } catch {
    // Range selector not found; skip
  }

  // ── 4. Screenshot the trends chart area ──
  try {
    const chartContainer = chefPage.locator('.insights-chart-container').first()
    await chartContainer.waitFor({ state: 'visible', timeout: 5000 })
    await chartContainer.scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage)
    await screenshot(chefPage, 'insights-trends-chart')
  } catch {
    // Chart area not visible
  }

  // ── 5. Screenshot the order breakdown / pie chart section ──
  try {
    const pieSection = chefPage.locator('.insights-pie-container').first()
    await pieSection.waitFor({ state: 'visible', timeout: 5000 })
    await pieSection.scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage)
    await screenshot(chefPage, 'insights-order-breakdown')
  } catch {
    // Pie chart section not rendered (no orders) — try the two-col layout
    try {
      const twoCol = chefPage.locator('.insights-two-col').first()
      await twoCol.waitFor({ state: 'visible', timeout: 3000 })
      await twoCol.scrollIntoViewIfNeeded().catch(() => {})
      await settle(chefPage)
      await screenshot(chefPage, 'insights-breakdown-section')
    } catch {
      // Section not present
    }
  }

  // ── 6. Open the analytics drawer from a clickable metric card ──
  try {
    // First try the insights-specific revenue cards
    let metricCard = chefPage.locator('.insights-metric-card').first()
    if ((await metricCard.count()) === 0) {
      // Fallback to the Today dashboard metric cards
      metricCard = chefPage.locator('.chef-metric-card.clickable', { hasText: 'Revenue' }).first()
    }

    if (await metricCard.count()) {
      await metricCard.scrollIntoViewIfNeeded().catch(() => {})
      await metricCard.click()
      await settle(chefPage, 600)

      // Wait for the analytics drawer to appear
      const drawer = chefPage.locator('.analytics-drawer.open')
      await drawer.waitFor({ state: 'visible', timeout: 8000 })
      await settle(chefPage, 500)
      await screenshot(chefPage, 'insights-analytics-drawer-open')

      // Close the drawer
      const closeBtn = chefPage.locator('.drawer-close-btn').first()
      if (await closeBtn.count()) {
        await closeBtn.click()
        await settle(chefPage, 400)
      }
    }
  } catch {
    // Analytics drawer interaction not available
  }

  // ── 7. Final full-page overview ──
  await chefPage.evaluate(() => window.scrollTo(0, 0))
  await settle(chefPage, 400)
  await screenshot(chefPage, 'insights-final-overview')
}
