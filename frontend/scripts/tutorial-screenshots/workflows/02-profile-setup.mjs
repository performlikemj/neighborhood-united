/**
 * Workflow 02 – Profile Setup
 *
 * Captures setting up the chef profile from scratch: filling in text
 * fields, uploading a profile picture and banner image, adding a
 * Calendly booking link, saving, and viewing service areas.
 * Starts from a freshly-reset chef account with an empty profile.
 */

export const meta = { name: 'Profile Setup', dir: '02_profile_setup' }

export default async function profileSetup(ctx) {
  const {
    chefPage,
    screenshot,
    openChefTab,
    waitForToast,
    resetToasts,
    settle,
    sampleImage,
    altImage,
  } = ctx

  // -----------------------------------------------------------------------
  // 1. Navigate to My Profile tab – screenshot empty profile form
  // -----------------------------------------------------------------------
  await openChefTab(chefPage, 'My Profile')
  await chefPage.waitForLoadState('networkidle')
  await settle(chefPage)
  await screenshot(chefPage, 'empty-profile-form')

  // -----------------------------------------------------------------------
  // 2. Fill in the Experience text
  // -----------------------------------------------------------------------
  const experienceTextarea = chefPage
    .locator('textarea[placeholder*="culinary experience"]')
    .first()
  await experienceTextarea.scrollIntoViewIfNeeded()
  await experienceTextarea.fill(
    'Award-winning chef with 15 years of experience in farm-to-table cuisine and Mediterranean cooking.',
  )
  await settle(chefPage, 300)

  // -----------------------------------------------------------------------
  // 3. Fill in the Bio text
  // -----------------------------------------------------------------------
  const bioTextarea = chefPage
    .locator('textarea[placeholder*="style and specialties"]')
    .first()
  await bioTextarea.scrollIntoViewIfNeeded()
  await bioTextarea.fill(
    'I specialize in crafting personalized meal plans that celebrate seasonal ingredients. My approach combines traditional techniques with modern nutrition science to create meals that are both delicious and nourishing.',
  )
  await settle(chefPage, 300)

  // -----------------------------------------------------------------------
  // 4. Screenshot after filling in both text fields
  // -----------------------------------------------------------------------
  await screenshot(chefPage, 'profile-text-fields-filled')

  // -----------------------------------------------------------------------
  // 5. Upload profile picture using sampleImage
  // -----------------------------------------------------------------------
  // FileSelect uses a hidden <input type="file">. The profile picture is the
  // first FileSelect inside the profile card. We target via the label text.
  const profileCard = chefPage.locator('.card', { hasText: 'Chef profile' }).first()
  const fileInputs = profileCard.locator('input[type="file"]')

  // First file input is for the profile picture
  const profilePicInput = fileInputs.nth(0)
  await profilePicInput.setInputFiles(sampleImage)
  await settle(chefPage)
  await screenshot(chefPage, 'profile-picture-selected')

  // -----------------------------------------------------------------------
  // 6. Upload banner image using altImage
  // -----------------------------------------------------------------------
  // Second file input is for the banner image
  const bannerInput = fileInputs.nth(1)
  await bannerInput.setInputFiles(altImage)
  await settle(chefPage)
  await screenshot(chefPage, 'banner-image-selected')

  // -----------------------------------------------------------------------
  // 7. Fill in Calendly URL and screenshot
  // -----------------------------------------------------------------------
  const calendlyInput = chefPage
    .locator('input[placeholder*="calendly.com"]')
    .first()
  await calendlyInput.scrollIntoViewIfNeeded()
  await calendlyInput.fill('https://calendly.com/ferris/consultation')
  await settle(chefPage, 300)
  await screenshot(chefPage, 'calendly-url-filled')

  // -----------------------------------------------------------------------
  // 8. Click Save Changes, wait for the save to complete, screenshot
  // -----------------------------------------------------------------------
  await resetToasts(chefPage)
  const saveBtn = profileCard
    .getByRole('button', { name: /Save changes/i })
    .first()
  await saveBtn.scrollIntoViewIfNeeded()
  await saveBtn.click()

  // Wait for the save to finish: button text reverts from "Saving..." back
  await chefPage
    .locator('button', { hasText: /Save changes/i })
    .first()
    .waitFor({ timeout: 15000 })
  await settle(chefPage)
  await screenshot(chefPage, 'profile-saved')

  // -----------------------------------------------------------------------
  // 9. Scroll down to the Service Areas section and screenshot
  // -----------------------------------------------------------------------
  const serviceAreasCard = chefPage
    .locator('.card', { hasText: 'Service Areas' })
    .first()
  await serviceAreasCard.scrollIntoViewIfNeeded()
  await settle(chefPage)
  await screenshot(chefPage, 'service-areas-section')

  // -----------------------------------------------------------------------
  // 10. Click "Request New Areas" to open the service area picker
  // -----------------------------------------------------------------------
  const requestAreasBtn = serviceAreasCard
    .getByRole('button', { name: /Request New Areas/i })
    .first()
  await requestAreasBtn.click()
  await settle(chefPage)
  await screenshot(chefPage, 'service-area-picker-open')

  // -----------------------------------------------------------------------
  // 11. Close the picker by clicking Cancel
  // -----------------------------------------------------------------------
  const cancelBtn = serviceAreasCard
    .getByRole('button', { name: /Cancel/i })
    .first()
  if (await cancelBtn.isVisible().catch(() => false)) {
    await cancelBtn.click()
    await settle(chefPage)
  }
}
