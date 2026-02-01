/**
 * Workflow 07 – Order Management
 *
 * Captures the Orders tab with its filter toolbar, demonstrating
 * search, type filter, status filter, sort, clear, and refresh.
 */

export const meta = { name: 'Order Management', dir: '07_orders' }

export default async function capture(ctx) {
  const { chefPage, screenshot, openChefTab, settle } = ctx

  // 1. Navigate to Orders tab and screenshot the initial view
  await openChefTab(chefPage, 'Orders')
  await chefPage.locator('.chef-orders-toolbar').waitFor({ state: 'visible', timeout: 10000 }).catch(() => {})
  await settle(chefPage)
  await screenshot(chefPage, 'orders-overview')

  // 2. Screenshot the filter toolbar showing all controls
  const toolbar = chefPage.locator('.chef-orders-toolbar')
  if (await toolbar.count().catch(() => 0)) {
    await toolbar.scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage, 400)
    await screenshot(chefPage, 'orders-filter-toolbar')
  }

  // 3. Type "test" in the search input and screenshot
  const searchInput = chefPage.locator('input#chef-orders-search')
  await searchInput.fill('test')
  await settle(chefPage)
  await screenshot(chefPage, 'orders-search-active')

  // 4. Change the type filter to "meal" and screenshot
  const typeSelect = chefPage.locator('select#chef-orders-type')
  await typeSelect.selectOption('meal')
  await settle(chefPage)
  await screenshot(chefPage, 'orders-type-meal-filter')

  // 5. Change the status filter to "completed" and screenshot
  const statusSelect = chefPage.locator('select#chef-orders-status')
  await statusSelect.selectOption('completed')
  await settle(chefPage)
  await screenshot(chefPage, 'orders-status-completed-filter')

  // 6. Change the sort to "oldest" and screenshot
  const sortSelect = chefPage.locator('select#chef-orders-sort')
  await sortSelect.selectOption('oldest')
  await settle(chefPage)
  await screenshot(chefPage, 'orders-sort-oldest')

  // 7. Click "Clear filters" button and screenshot the reset state
  const clearBtn = chefPage.getByRole('button', { name: /clear filters/i })
  if (await clearBtn.isVisible().catch(() => false)) {
    await clearBtn.click()
    await settle(chefPage)
  } else {
    // Filters may already be cleared if none were active; reset manually
    await searchInput.fill('')
    await typeSelect.selectOption('all')
    await statusSelect.selectOption('all')
    await sortSelect.selectOption('newest')
    await settle(chefPage)
  }
  await screenshot(chefPage, 'orders-filters-cleared')

  // 8. Click the Refresh button and screenshot
  const refreshBtn = chefPage.getByRole('button', { name: /refresh/i })
  if (await refreshBtn.isVisible().catch(() => false)) {
    await refreshBtn.click()
    await settle(chefPage, 800)
  }
  await screenshot(chefPage, 'orders-refreshed')
}
