/**
 * Workflow 04 – Menu Builder
 *
 * Captures the full menu-building journey: adding ingredients, composing
 * a dish from those ingredients, and creating a meal that references the dish.
 * Starts from an empty kitchen (data was reset before the capture run).
 *
 * IMPORTANT: The Menu Builder tab has sub-tabs (Ingredients, Dishes, Meals).
 * Only one sub-tab is rendered at a time — we must click between them.
 */

export const meta = { name: 'Menu Builder', dir: '04_menu_builder' }

export default async function menuBuilder(ctx) {
  const { chefPage, screenshot, openChefTab, waitForToast, resetToasts, settle } = ctx

  // -----------------------------------------------------------------------
  // Helper to switch sub-tabs within the Menu Builder
  // -----------------------------------------------------------------------
  async function switchSubTab(label) {
    const btn = chefPage.locator('.sub-tab', { hasText: label }).first()
    await btn.click()
    await settle(chefPage)
  }

  // -----------------------------------------------------------------------
  // 1. Open Menu Builder tab – empty kitchen
  // -----------------------------------------------------------------------
  await openChefTab(chefPage, 'Menu Builder')
  await chefPage.waitForLoadState('networkidle')
  await settle(chefPage)
  await screenshot(chefPage, 'empty-kitchen')

  // -----------------------------------------------------------------------
  // 2. Ingredients sub-tab — open Add form
  // -----------------------------------------------------------------------
  await switchSubTab('Ingredients')
  const ingredientSection = chefPage
    .locator('.chef-kitchen-section')
    .first()
  await ingredientSection.getByRole('button', { name: /Add/i }).click()
  await settle(chefPage)
  await screenshot(chefPage, 'ingredient-add-form')

  // -----------------------------------------------------------------------
  // 3. Fill first ingredient – Organic Chicken Breast, 165 cal
  // -----------------------------------------------------------------------
  await ingredientSection
    .locator('input[placeholder*="Chicken"], input[placeholder*="ingredient"]')
    .first()
    .fill('Organic Chicken Breast')
  await ingredientSection.locator('input[type="number"]').first().fill('165')
  await settle(chefPage)
  await screenshot(chefPage, 'ingredient-filled-chicken')

  // -----------------------------------------------------------------------
  // 4. Create the first ingredient
  // -----------------------------------------------------------------------
  await resetToasts(chefPage)
  await ingredientSection
    .getByRole('button', { name: /Add Ingredient/i })
    .click()
  await waitForToast(chefPage, 'Ingredient created')
  await settle(chefPage)
  await screenshot(chefPage, 'ingredient-list-chicken-added')

  // -----------------------------------------------------------------------
  // 5. Add second ingredient – Fresh Basil, 23 cal
  // -----------------------------------------------------------------------
  await resetToasts(chefPage)
  await ingredientSection
    .locator('input[placeholder*="Chicken"], input[placeholder*="ingredient"]')
    .first()
    .fill('Fresh Basil')
  await ingredientSection.locator('input[type="number"]').first().fill('23')
  await ingredientSection
    .getByRole('button', { name: /Add Ingredient/i })
    .click()
  await waitForToast(chefPage, 'Ingredient created')
  await settle(chefPage)
  await screenshot(chefPage, 'ingredient-list-basil-added')

  // -----------------------------------------------------------------------
  // 6. Switch to Dishes sub-tab, open Add form
  // -----------------------------------------------------------------------
  await switchSubTab('Dishes')
  await settle(chefPage)

  const addDishBtn = chefPage.getByRole('button', { name: /Add/i }).first()
  await addDishBtn.click()
  await settle(chefPage)
  await screenshot(chefPage, 'dish-add-form')

  // -----------------------------------------------------------------------
  // 7. Fill dish – Herb-Crusted Chicken, select both ingredients
  // -----------------------------------------------------------------------
  await chefPage.locator('input[placeholder*="Salmon"], input[placeholder*="dish"], input.input').first().fill('Herb-Crusted Chicken')
  const ingredientSelect = chefPage.locator('select.select[multiple]')
  await ingredientSelect.waitFor({ timeout: 10000 })
  await ingredientSelect.selectOption([
    { label: 'Organic Chicken Breast' },
    { label: 'Fresh Basil' },
  ])
  await settle(chefPage)
  await screenshot(chefPage, 'dish-filled-herb-crusted-chicken')

  // -----------------------------------------------------------------------
  // 8. Create the dish
  // -----------------------------------------------------------------------
  await resetToasts(chefPage)
  await chefPage
    .getByRole('button', { name: /Create Dish/i })
    .click()
  // Wait for the dish to appear in the list
  await chefPage.waitForTimeout(2000)
  await settle(chefPage)
  await screenshot(chefPage, 'dishes-list-with-herb-crusted-chicken')

  // -----------------------------------------------------------------------
  // 9. Switch to Meals sub-tab, open Add form
  // -----------------------------------------------------------------------
  await switchSubTab('Meals')
  await settle(chefPage)

  const addMealBtn = chefPage.getByRole('button', { name: /Add/i }).first()
  await addMealBtn.click()
  await settle(chefPage)
  await screenshot(chefPage, 'meal-add-form')

  // -----------------------------------------------------------------------
  // 10. Fill meal – Mediterranean Dinner
  // -----------------------------------------------------------------------
  await chefPage
    .locator('input[placeholder*="Sunday"], input[placeholder*="meal"]')
    .first()
    .fill('Mediterranean Dinner')
  const mealTextarea = chefPage.locator('textarea').first()
  if (await mealTextarea.isVisible().catch(() => false)) {
    await mealTextarea.fill(
      'A vibrant Mediterranean-inspired dinner featuring herb-crusted chicken with fresh seasonal sides.',
    )
  }
  // Select meal type
  const mealTypeSelect = chefPage.locator('select').first()
  if (await mealTypeSelect.isVisible().catch(() => false)) {
    await mealTypeSelect.selectOption('Dinner')
  }
  // Set price
  const priceInput = chefPage.locator('.label:has-text("Price") + input')
  if (await priceInput.count()) {
    await priceInput.fill('25')
  }
  // Check the dish checkbox
  const dishCheckbox = chefPage.getByLabel('Herb-Crusted Chicken')
  if (await dishCheckbox.count()) {
    await dishCheckbox.click()
  }
  await settle(chefPage)
  await screenshot(chefPage, 'meal-filled-mediterranean-dinner')

  // -----------------------------------------------------------------------
  // 11. Create the meal
  // -----------------------------------------------------------------------
  await resetToasts(chefPage)
  await chefPage
    .getByRole('button', { name: /Create Meal/i })
    .click()
  await chefPage.waitForTimeout(2000)
  await settle(chefPage)
  await screenshot(chefPage, 'meal-card-mediterranean-dinner')

  // -----------------------------------------------------------------------
  // 12. Open meal slideout detail view (if meal card exists)
  // -----------------------------------------------------------------------
  const mealCard = chefPage
    .locator('.chef-item-card', { hasText: 'Mediterranean Dinner' })
    .first()
  if (await mealCard.count()) {
    await mealCard.click()
    await chefPage.locator('.meal-slideout').waitFor({ timeout: 10000 }).catch(() => {})
    await settle(chefPage)
    await screenshot(chefPage, 'meal-slideout-detail')
  }
}
