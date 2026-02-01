/**
 * Workflow 05 – Services & Pricing
 *
 * Creates a service offering with two pricing tiers.
 * Starts with no existing services (data was reset before the capture run).
 */

export const meta = { name: 'Services & Pricing', dir: '05_services_pricing' }

export default async function servicesPricing(ctx) {
  const { chefPage, screenshot, openChefTab, waitForToast, resetToasts, settle } = ctx

  // -----------------------------------------------------------------------
  // 1. Open Services tab – empty / initial view
  // -----------------------------------------------------------------------
  await openChefTab(chefPage, 'Services')
  await chefPage.waitForLoadState('networkidle')
  await settle(chefPage)
  await screenshot(chefPage, 'services-empty')

  // -----------------------------------------------------------------------
  // 2. Fill the service creation form
  // -----------------------------------------------------------------------
  const serviceForm = chefPage
    .locator('.card', { hasText: 'Create service offering' })
    .first()

  await serviceForm
    .locator('.label:has-text("Title") + input')
    .fill('Weekly Meal Prep')
  await serviceForm
    .locator('.label:has-text("Description") + textarea')
    .fill(
      "Professional weekly meal preparation tailored to your family's dietary needs and preferences.",
    )
  await serviceForm
    .locator('.label:has-text("Default duration") + input')
    .fill('120')
  await serviceForm
    .locator('.label:has-text("Max travel miles") + input')
    .fill('15')
  await settle(chefPage)
  await screenshot(chefPage, 'service-form-filled')

  // -----------------------------------------------------------------------
  // 3. Create the service offering
  // -----------------------------------------------------------------------
  await resetToasts(chefPage)
  await serviceForm
    .getByRole('button', { name: /Create offering/i })
    .click()
  await waitForToast(chefPage, 'Service offering created')
  await chefPage
    .locator('h4', { hasText: 'Weekly Meal Prep' })
    .first()
    .waitFor({ timeout: 15000 })
  await settle(chefPage)
  await screenshot(chefPage, 'service-created')

  // Locate the newly created service card for tier operations
  const serviceCard = chefPage
    .locator('.card')
    .filter({ has: chefPage.getByRole('heading', { name: 'Weekly Meal Prep' }) })
    .first()

  // -----------------------------------------------------------------------
  // 4. Click "Add tier" and screenshot the tier form
  // -----------------------------------------------------------------------
  await serviceCard.getByRole('button', { name: /Add tier/i }).first().click()
  await settle(chefPage)
  await screenshot(chefPage, 'tier-form-open')

  // -----------------------------------------------------------------------
  // 5. Fill first tier – household 1-2, $150
  // -----------------------------------------------------------------------
  const tierForm = chefPage
    .locator('form', { hasText: 'Create tier' })
    .first()

  await tierForm
    .locator('.label:has-text("Household min") + input')
    .fill('1')
  await tierForm
    .locator('.label:has-text("Household max") + input')
    .fill('2')
  await tierForm.locator('.label:has-text("Price") + input').fill('150')
  await settle(chefPage)
  await screenshot(chefPage, 'tier1-filled')

  // -----------------------------------------------------------------------
  // 6. Create first tier
  // -----------------------------------------------------------------------
  await resetToasts(chefPage)
  await tierForm.getByRole('button', { name: /Create tier/i }).click()
  await waitForToast(chefPage, 'Tier created')
  await settle(chefPage)
  await screenshot(chefPage, 'service-with-tier1')

  // -----------------------------------------------------------------------
  // 7. Add second tier – household 3-6, $250
  // -----------------------------------------------------------------------
  await serviceCard.getByRole('button', { name: /Add tier/i }).first().click()
  await settle(chefPage)

  const tierForm2 = chefPage
    .locator('form', { hasText: 'Create tier' })
    .first()

  await tierForm2
    .locator('.label:has-text("Household min") + input')
    .fill('3')
  await tierForm2
    .locator('.label:has-text("Household max") + input')
    .fill('6')
  await tierForm2.locator('.label:has-text("Price") + input').fill('250')

  await resetToasts(chefPage)
  await tierForm2.getByRole('button', { name: /Create tier/i }).click()
  await waitForToast(chefPage, 'Tier created')
  await settle(chefPage)
  await screenshot(chefPage, 'service-with-tier2-created')

  // -----------------------------------------------------------------------
  // 8. Final screenshot of complete service card with both tiers
  // -----------------------------------------------------------------------
  await settle(chefPage, 400)
  await screenshot(chefPage, 'service-complete-both-tiers')
}
