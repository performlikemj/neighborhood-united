/**
 * Workflow 08 – Client Management (CRM)
 *
 * Captures the Clients tab, then drives a customer connection request
 * from the customer page, switches back to the chef page to accept it,
 * and screenshots each step of the flow.
 */

export const meta = { name: 'Client Management', dir: '08_clients_crm' }

export default async function capture(ctx) {
  const {
    chefPage,
    customerPage,
    baseUrl,
    screenshot,
    openChefTab,
    waitForToast,
    resetToasts,
    settle,
  } = ctx

  // ── 1. Navigate to Clients tab on chef page ──────────────────────
  await openChefTab(chefPage, 'Clients')
  await chefPage.getByRole('heading', { name: /client connections/i })
    .waitFor({ state: 'visible', timeout: 10000 }).catch(() => {})
  await settle(chefPage)
  await screenshot(chefPage, 'clients-heading')

  // ── 2. Screenshot the initial state (empty or with existing connections) ──
  await screenshot(chefPage, 'clients-initial-state')

  // ── 3. Customer: go to chefs directory, search for "ferris" ──────
  await customerPage.goto(`${baseUrl}/chefs`)
  await customerPage.waitForLoadState('networkidle').catch(() => {})
  await settle(customerPage)

  const searchInput = customerPage.locator('.search-input').first()
  await searchInput.waitFor({ state: 'visible', timeout: 8000 }).catch(() => {})
  await searchInput.fill('ferris')
  await settle(customerPage, 800)
  await screenshot(customerPage, 'customer-search-ferris')

  // ── 4. Customer: click on ferris's profile and screenshot ────────
  // Look for a link/card that contains "ferris" (case-insensitive)
  const chefCard = customerPage.locator('a, [role="link"], .chef-card, .chef-list-item')
    .filter({ hasText: /ferris/i })
    .first()

  if (await chefCard.isVisible().catch(() => false)) {
    await chefCard.click()
  } else {
    // Fallback: navigate directly to ferris's public profile
    await customerPage.goto(`${baseUrl}/chefs/ferris`)
  }

  // Wait for the public chef profile heading to appear
  await customerPage.getByRole('heading', { name: /ferris/i })
    .waitFor({ state: 'visible', timeout: 10000 }).catch(() => {})
  await customerPage.waitForLoadState('networkidle').catch(() => {})
  await settle(customerPage)
  await screenshot(customerPage, 'customer-chef-public-profile')

  // ── 5. Customer: request invitation if button exists ─────────────
  await resetToasts(customerPage)
  const requestBtn = customerPage.getByRole('button', { name: /request invitation/i }).first()
  const heroAddBtn = customerPage.locator('.hero-add-btn:not(.pending)').first()
  const stickyAddBtn = customerPage.locator('.sticky-add-btn:not(.pending)').first()

  let requestSent = false
  if (await requestBtn.isVisible().catch(() => false)) {
    await requestBtn.click()
    requestSent = true
  } else if (await heroAddBtn.isVisible().catch(() => false)) {
    await heroAddBtn.click()
    requestSent = true
  } else if (await stickyAddBtn.isVisible().catch(() => false)) {
    await stickyAddBtn.click()
    requestSent = true
  }

  if (requestSent) {
    await waitForToast(customerPage, 'Invitation request sent').catch(() => {})
    await settle(customerPage)
  }
  await screenshot(customerPage, 'customer-invitation-requested')

  // ── 6. Chef: open Clients tab and look for the pending connection ──
  await openChefTab(chefPage, 'Clients')
  await settle(chefPage, 1000)
  // Wait for client list content to load
  await chefPage.getByRole('heading', { name: /client connections/i })
    .waitFor({ state: 'visible', timeout: 10000 }).catch(() => {})
  await settle(chefPage)

  // Look for customer "kiho" text somewhere in the page
  const kihoText = chefPage.locator('text=kiho').first()
  await kihoText.waitFor({ state: 'visible', timeout: 8000 }).catch(() => {})
  await screenshot(chefPage, 'chef-pending-connection')

  // ── 7. Click on kiho row, accept if possible ─────────────────────
  await resetToasts(chefPage)

  // Try clicking on a pending connection card/row containing "kiho"
  const pendingCard = chefPage.locator('.cc-pending-card, .client-row, [class*="client"], [class*="connection"]')
    .filter({ hasText: /kiho/i })
    .first()

  if (await pendingCard.isVisible().catch(() => false)) {
    await pendingCard.click().catch(() => {})
    await settle(chefPage, 400)
  }

  // Look for an Accept button (in pending requests banner or detail panel)
  const acceptBtn = chefPage.locator('button')
    .filter({ hasText: /accept/i })
    .first()

  if (await acceptBtn.isVisible().catch(() => false)) {
    await acceptBtn.click()
    await waitForToast(chefPage, 'Connection accepted').catch(() => {})
    await settle(chefPage)
  }
  await screenshot(chefPage, 'chef-connection-accepted')

  // ── 8. Screenshot the active client details panel ────────────────
  // After acceptance, a detail view or updated client list may be showing
  const detailPanel = chefPage.locator('.client-detail, .cc-detail, [class*="detail-panel"], [class*="client-detail"]').first()
  if (await detailPanel.isVisible().catch(() => false)) {
    await detailPanel.scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage, 400)
    await screenshot(chefPage, 'client-details-panel')
  } else {
    // Detail panel not visible -- just screenshot current state as the final view
    await settle(chefPage, 400)
    await screenshot(chefPage, 'clients-final-state')
  }
}
