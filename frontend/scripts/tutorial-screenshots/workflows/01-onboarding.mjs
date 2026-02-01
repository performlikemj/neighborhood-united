/**
 * Workflow 01 – Onboarding Checklist
 *
 * Captures the onboarding checklist that appears on the Today dashboard
 * when a chef has not completed all activation steps. Starts from a
 * freshly-reset chef account so every step shows as incomplete.
 */

export const meta = { name: 'Onboarding Checklist', dir: '01_onboarding' }

export default async function onboarding(ctx) {
  const { chefPage, screenshot, openChefTab, settle } = ctx

  // -----------------------------------------------------------------------
  // 1. Navigate to the Today dashboard – full page with onboarding checklist
  // -----------------------------------------------------------------------
  await openChefTab(chefPage, 'Today')
  await chefPage.waitForLoadState('networkidle')
  await settle(chefPage)
  await screenshot(chefPage, 'today-dashboard-with-onboarding')

  // -----------------------------------------------------------------------
  // 2. Screenshot the onboarding checklist steps area
  // -----------------------------------------------------------------------
  const checklist = chefPage.locator('.onboarding-checklist').first()
  // The checklist may not be present if the chef happens to be fully set up,
  // so fall back to the today-onboarding card inside TodayDashboard.
  const hasChecklist = await checklist.count() > 0
  if (hasChecklist) {
    await checklist.scrollIntoViewIfNeeded()
    await settle(chefPage)
    await screenshot(chefPage, 'onboarding-checklist-steps', { fullPage: false })
  } else {
    // Fall back to the onboarding progress card in TodayDashboard
    const onboardingCard = chefPage.locator('.today-onboarding').first()
    if (await onboardingCard.count() > 0) {
      await onboardingCard.scrollIntoViewIfNeeded()
      await settle(chefPage)
      await screenshot(chefPage, 'onboarding-progress-card', { fullPage: false })
    }
  }

  // -----------------------------------------------------------------------
  // 3. Check for "Go Live" / "Start Cooking!" button (disabled state)
  // -----------------------------------------------------------------------
  const goLiveBtn = chefPage
    .locator('.onboarding-complete.go-live')
    .first()
  if (await goLiveBtn.count() > 0) {
    await goLiveBtn.scrollIntoViewIfNeeded()
    await settle(chefPage)
    await screenshot(chefPage, 'go-live-button-state')
  }

  // -----------------------------------------------------------------------
  // 4. Screenshot the break mode toggle area
  // -----------------------------------------------------------------------
  const breakSection = chefPage.locator('.today-break-section').first()
  if (await breakSection.count() > 0) {
    await breakSection.scrollIntoViewIfNeeded()
    await settle(chefPage)
    await screenshot(chefPage, 'break-mode-toggle')
  } else {
    // The break card may also appear as .today-break-card directly
    const breakCard = chefPage.locator('.today-break-card').first()
    if (await breakCard.count() > 0) {
      await breakCard.scrollIntoViewIfNeeded()
      await settle(chefPage)
      await screenshot(chefPage, 'break-mode-toggle')
    }
  }
}
