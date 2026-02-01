/**
 * Workflow 10 - Payment Links
 *
 * Captures the payment links management interface including
 * stats cards, create modal, existing link list, and filters.
 */

export const meta = { name: 'Payment Links', dir: '10_payment_links' }

export default async function capture(ctx) {
  const { chefPage, screenshot, openChefTab, settle } = ctx

  // 1. Navigate to Payment Links tab and screenshot the initial view
  await openChefTab(chefPage, 'Payment Links')
  await chefPage.getByRole('heading', { name: /Payment Links/i }).waitFor({ timeout: 15000 })
  await settle(chefPage)
  await screenshot(chefPage, 'payment-links-overview')

  // 2. Screenshot stats/summary cards if present (Total Links, Pending, Paid, etc.)
  const statCards = chefPage.locator('div', { hasText: 'Total Links' })
  if (await statCards.count()) {
    await screenshot(chefPage, 'payment-links-stats')
  }

  // 3. Look for the "Create Payment Link" button and open the create modal
  const createBtn = chefPage.locator('button', { hasText: 'Create Payment Link' })
  if (await createBtn.count()) {
    await createBtn.scrollIntoViewIfNeeded().catch(() => {})
    await screenshot(chefPage, 'create-payment-link-button')

    // Click to open the create modal
    await createBtn.click()
    await settle(chefPage, 600)

    // Wait for the modal to appear
    const modal = chefPage.locator('h3', { hasText: 'Create Payment Link' })
    if (await modal.count()) {
      await screenshot(chefPage, 'create-payment-link-modal')

      // Fill the form: amount and description
      const amountInput = chefPage.locator('input[type="number"]').first()
      const descriptionInput = chefPage.locator('input[placeholder*="meal prep"]').first()

      // Try the amount field
      if (await amountInput.count()) {
        await amountInput.fill('75')
      }

      // Try the description field - use a broader selector if placeholder doesn't match
      if (await descriptionInput.count()) {
        await descriptionInput.fill('Weekly meal prep service - Johnson family')
      } else {
        // Fallback: find the description input by label
        const descByLabel = chefPage.locator('label', { hasText: 'Description' })
          .locator('..')
          .locator('input[type="text"]')
          .first()
        if (await descByLabel.count()) {
          await descByLabel.fill('Weekly meal prep service - Johnson family')
        }
      }

      await settle(chefPage, 400)
      await screenshot(chefPage, 'create-form-filled')

      // Close the modal without submitting
      const closeBtn = chefPage.locator('button', { hasText: 'Cancel' }).first()
      if (await closeBtn.count()) {
        await closeBtn.click()
        await settle(chefPage, 400)
      } else {
        // Fallback: click the X button
        const xBtn = chefPage.locator('button:has-text("×")').first()
        if (await xBtn.count()) {
          await xBtn.click()
          await settle(chefPage, 400)
        }
      }
    }
  }

  // 4. Screenshot existing payment links list if any exist
  try {
    const linkRows = chefPage.locator('div[style*="borderBottom"]', { hasText: 'Created' })
    if (await linkRows.count()) {
      await screenshot(chefPage, 'payment-links-list')

      // Click the first link to show the detail panel
      await linkRows.first().click()
      await settle(chefPage, 500)
      await screenshot(chefPage, 'payment-link-detail')
    }
  } catch {
    // No existing links - that is fine
  }

  // 5. Screenshot the empty state if no links exist
  const emptyState = chefPage.locator('text=No payment links found')
  if (await emptyState.count()) {
    await screenshot(chefPage, 'payment-links-empty-state')
  }
}
