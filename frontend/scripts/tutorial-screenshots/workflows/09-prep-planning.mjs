/**
 * Workflow 09 - Prep Planning
 *
 * Captures the prep planning / shopping list interface including
 * day-range selectors, shopping list grouped by storage type,
 * commitment cards, and summary cards.
 */

export const meta = { name: 'Prep Planning', dir: '09_prep_planning' }

export default async function capture(ctx) {
  const { chefPage, screenshot, openChefTab, settle } = ctx

  // 1. Navigate to the Prep Planning tab and screenshot the overview
  await openChefTab(chefPage, 'Prep Planning')
  await chefPage.getByRole('heading', { name: 'Prep Planning' }).waitFor({ timeout: 15000 })
  await settle(chefPage)
  await screenshot(chefPage, 'prep-planning-overview')

  // 2. Screenshot the day-range selector buttons (7, 14, 21, 30)
  const dayButtons = chefPage.locator('button.btn-sm', { hasText: /^(7|14|21|30)$/ })
  const dayButtonCount = await dayButtons.count()
  if (dayButtonCount > 0) {
    await dayButtons.first().scrollIntoViewIfNeeded().catch(() => {})
    await screenshot(chefPage, 'day-range-selector')

    // Click a different range (14 days) to show interactivity
    const btn14 = chefPage.locator('button.btn-sm', { hasText: '14' })
    if (await btn14.count()) {
      await btn14.click()
      await settle(chefPage, 800)
      await screenshot(chefPage, 'day-range-14-selected')
    }
  }

  // Determine whether we have data or an empty state
  const emptyState = chefPage.locator('text=No Upcoming Meals')
  const hasData = (await emptyState.count()) === 0

  if (hasData) {
    // 3. Shopping list items grouped by storage type (Refrigerated, Frozen, Pantry, Counter)
    const shoppingSection = chefPage.locator('h3', { hasText: 'Shopping List' })
    if (await shoppingSection.count()) {
      await shoppingSection.scrollIntoViewIfNeeded().catch(() => {})

      // Switch to category grouping to show storage type groups
      const categoryBtn = chefPage.locator('button.btn-sm', { hasText: 'Category' })
      if (await categoryBtn.count()) {
        await categoryBtn.click()
        await settle(chefPage, 800)
        await screenshot(chefPage, 'shopping-list-by-category')
      }

      // Switch back to date grouping
      const dateBtn = chefPage.locator('button.btn-sm', { hasText: 'Date' })
      if (await dateBtn.count()) {
        await dateBtn.click()
        await settle(chefPage, 800)
        await screenshot(chefPage, 'shopping-list-by-date')
      }
    }

    // 4. Commitment cards (Upcoming Meals section)
    const upcomingMeals = chefPage.locator('h3', { hasText: 'Upcoming Meals' })
    if (await upcomingMeals.count()) {
      await upcomingMeals.scrollIntoViewIfNeeded().catch(() => {})
      await screenshot(chefPage, 'upcoming-meals-commitments')
    }

    // 5. Summary cards (Meals, Servings, Clients, Ingredients)
    const summaryGrid = chefPage.locator('.grid.grid-4').first()
    if (await summaryGrid.count()) {
      await summaryGrid.scrollIntoViewIfNeeded().catch(() => {})
      await screenshot(chefPage, 'summary-cards')
    }
  } else {
    // 6. Empty state - no upcoming meals
    await screenshot(chefPage, 'empty-state-no-meals')
  }
}
