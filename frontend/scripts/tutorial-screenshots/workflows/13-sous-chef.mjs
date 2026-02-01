/**
 * Workflow 13 – Sous Chef AI Assistant
 *
 * Captures the Sous Chef AI assistant interface including:
 * - Floating launcher button on the chef dashboard
 * - Widget panel (open state)
 * - Emoji picker interaction
 * - Full-page Sous Chef view
 * - Family selector / header area
 * - Chat input area
 */

export const meta = { name: 'Sous Chef AI Assistant', dir: '13_sous_chef' }

export default async function capture(ctx) {
  const { chefPage, baseUrl, screenshot, openChefTab, settle } = ctx

  // ── 1. Ensure we are on the chef dashboard showing the Sous Chef button ──
  await chefPage.goto(`${baseUrl}/chefs/dashboard`)
  await chefPage.waitForLoadState('networkidle').catch(() => {})
  await settle(chefPage, 800)
  // Wait for the launcher to be present
  await chefPage.getByRole('button', { name: 'Open Sous Chef' }).waitFor({ timeout: 10000 }).catch(() => {})
  await screenshot(chefPage, 'sous-chef-floating-button')

  // ── 2. Open the Sous Chef widget panel ──
  try {
    const openBtn = chefPage.getByRole('button', { name: 'Open Sous Chef' })
    await openBtn.click()
    // Wait for the panel heading to appear
    await chefPage.locator('.sc-header-title').waitFor({ state: 'visible', timeout: 8000 }).catch(() => {})
    await settle(chefPage, 600)
    await screenshot(chefPage, 'sous-chef-widget-panel-open')
  } catch {
    // Widget might not be available
  }

  // ── 3. Look for emoji trigger and click it ──
  try {
    const emojiTrigger = chefPage.locator('.emoji-trigger').first()
    await emojiTrigger.waitFor({ state: 'visible', timeout: 5000 })
    await emojiTrigger.click()
    await settle(chefPage, 500)
    await screenshot(chefPage, 'sous-chef-emoji-picker')
  } catch {
    // Emoji trigger not present in current UI
  }

  // ── 4. Click an emoji option if visible ──
  try {
    const emojiOptions = chefPage.locator('.emoji-option')
    if (await emojiOptions.count()) {
      await emojiOptions.nth(0).click()
      await settle(chefPage, 500)
      await screenshot(chefPage, 'sous-chef-emoji-changed')
    }
  } catch {
    // Emoji options not available
  }

  // ── 5. Close the widget panel ──
  try {
    // Try the close button in the panel header
    const closeBtn = chefPage.locator('.sc-close-btn').first()
    if (await closeBtn.isVisible().catch(() => false)) {
      await closeBtn.click()
      await settle(chefPage, 400)
    } else {
      // Fallback: try the sous-chef-panel close-btn selector from E2E tests
      const altClose = chefPage.locator('.sous-chef-panel .close-btn').first()
      if (await altClose.isVisible().catch(() => false)) {
        await altClose.click()
        await settle(chefPage, 400)
      } else {
        // Last resort: click the launcher toggle to close
        const launcher = chefPage.getByRole('button', { name: 'Close Sous Chef' })
        if (await launcher.isVisible().catch(() => false)) {
          await launcher.click()
          await settle(chefPage, 400)
        }
      }
    }
  } catch {
    // Panel might already be closed
  }

  // ── 6. Navigate to the full-page Sous Chef view ──
  await chefPage.goto(`${baseUrl}/chefs/dashboard/sous-chef`)
  await chefPage.waitForLoadState('networkidle').catch(() => {})
  await settle(chefPage, 800)

  // ── 7. Screenshot the full-page Sous Chef interface ──
  try {
    // Wait for the page title or main container
    await chefPage.locator('.sc-page-title').waitFor({ state: 'visible', timeout: 10000 }).catch(() => {})
    await screenshot(chefPage, 'sous-chef-full-page')
  } catch {
    // Still take a screenshot even if specific element not found
    await screenshot(chefPage, 'sous-chef-full-page-fallback')
  }

  // ── 8. Screenshot the family/client selector area in the header ──
  try {
    const clientSelector = chefPage.locator('.sc-page-client-selector').first()
    await clientSelector.waitFor({ state: 'visible', timeout: 5000 })
    await clientSelector.scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage)
    await screenshot(chefPage, 'sous-chef-family-selector')
  } catch {
    // Family selector not visible — try the header overall
    try {
      const header = chefPage.locator('.sc-page-header').first()
      await header.waitFor({ state: 'visible', timeout: 3000 })
      await screenshot(chefPage, 'sous-chef-header-area')
    } catch {
      // Header not found
    }
  }

  // ── 9. Screenshot the chat input area ──
  try {
    const chatInput = chefPage.locator('.sc-composer, .sc-composer-input, textarea').first()
    await chatInput.waitFor({ state: 'visible', timeout: 5000 })
    await chatInput.scrollIntoViewIfNeeded().catch(() => {})
    await settle(chefPage)
    await screenshot(chefPage, 'sous-chef-chat-input')
  } catch {
    // Chat input area might not be visible without scrolling
    try {
      const chatContainer = chefPage.locator('.sc-page-chat-container').first()
      await chatContainer.waitFor({ state: 'visible', timeout: 3000 })
      await screenshot(chefPage, 'sous-chef-chat-container')
    } catch {
      // Chat container not available
    }
  }

  // ── 10. Navigate back to the main dashboard ──
  await chefPage.goto(`${baseUrl}/chefs/dashboard`)
  await chefPage.waitForLoadState('networkidle').catch(() => {})
  await settle(chefPage, 500)
}
