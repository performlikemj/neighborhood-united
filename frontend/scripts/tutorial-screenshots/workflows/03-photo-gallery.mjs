/**
 * Workflow 03 – Photo Gallery
 *
 * Captures the photo gallery management workflow: viewing the empty
 * gallery, uploading photos with titles and captions, and marking
 * a photo as featured. Starts from a freshly-reset chef account
 * with no gallery photos.
 */

export const meta = { name: 'Photo Gallery', dir: '03_photo_gallery' }

export default async function photoGallery(ctx) {
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
  // 1. Navigate to My Profile tab, then click the Photos sub-tab
  // -----------------------------------------------------------------------
  await openChefTab(chefPage, 'My Profile')
  await chefPage.waitForLoadState('networkidle')
  await settle(chefPage)

  // Click the Photos sub-tab
  const photosSubTab = chefPage
    .locator('.sub-tab', { hasText: 'Photos' })
    .first()
  await photosSubTab.click()
  await settle(chefPage)
  await screenshot(chefPage, 'empty-gallery')

  // -----------------------------------------------------------------------
  // 2. Screenshot the upload card area
  // -----------------------------------------------------------------------
  const uploadCard = chefPage.locator('[data-testid="photo-upload-card"]').first()
  await uploadCard.scrollIntoViewIfNeeded()
  await settle(chefPage)
  await screenshot(chefPage, 'upload-card-area', { fullPage: false })

  // -----------------------------------------------------------------------
  // 3. Set file input, fill title and caption for first photo
  // -----------------------------------------------------------------------
  // The photo upload card has a hidden file input inside a FileSelect
  const photoFileInput = uploadCard.locator('input[type="file"]').first()
  await photoFileInput.setInputFiles(sampleImage)
  await settle(chefPage, 300)

  const titleInput = chefPage.locator('[data-testid="photo-title"]').first()
  await titleInput.fill('Signature Mediterranean Bowl')

  const captionInput = chefPage.locator('[data-testid="photo-caption"]').first()
  await captionInput.fill('Fresh seasonal ingredients')

  await settle(chefPage)
  await screenshot(chefPage, 'first-photo-form-filled')

  // -----------------------------------------------------------------------
  // 4. Click Upload, wait for toast, screenshot gallery with first photo
  // -----------------------------------------------------------------------
  await resetToasts(chefPage)
  const uploadBtn = uploadCard
    .getByRole('button', { name: /Upload/i })
    .first()
  await uploadBtn.click()
  await waitForToast(chefPage, 'Photo uploaded')
  await settle(chefPage)
  await screenshot(chefPage, 'gallery-first-photo-uploaded')

  // -----------------------------------------------------------------------
  // 5. Upload a second photo
  // -----------------------------------------------------------------------
  // The form resets after successful upload, so we fill it again
  const photoFileInput2 = uploadCard.locator('input[type="file"]').first()
  await photoFileInput2.setInputFiles(altImage)
  await settle(chefPage, 300)

  const titleInput2 = chefPage.locator('[data-testid="photo-title"]').first()
  await titleInput2.fill('Farm Fresh Ingredients')

  const captionInput2 = chefPage.locator('[data-testid="photo-caption"]').first()
  await captionInput2.fill('Locally sourced produce')

  await resetToasts(chefPage)
  const uploadBtn2 = uploadCard
    .getByRole('button', { name: /Upload/i })
    .first()
  await uploadBtn2.click()
  await waitForToast(chefPage, 'Photo uploaded')
  await settle(chefPage)
  await screenshot(chefPage, 'gallery-second-photo-uploaded')

  // -----------------------------------------------------------------------
  // 6. Upload a third photo with Featured checked (need 3+ for onboarding)
  // -----------------------------------------------------------------------
  const photoFileInput3 = uploadCard.locator('input[type="file"]').first()
  await photoFileInput3.setInputFiles(sampleImage)
  await settle(chefPage, 300)

  const titleInput3 = chefPage.locator('[data-testid="photo-title"]').first()
  await titleInput3.fill('Plated Perfection')

  const captionInput3 = chefPage.locator('[data-testid="photo-caption"]').first()
  await captionInput3.fill('Ready to serve')

  // Check the Featured checkbox
  const featuredCheckbox = chefPage.getByLabel('Featured')
  await featuredCheckbox.check()

  await settle(chefPage)

  await resetToasts(chefPage)
  const uploadBtn3 = uploadCard
    .getByRole('button', { name: /Upload/i })
    .first()
  await uploadBtn3.click()
  await waitForToast(chefPage, 'Photo uploaded')
  await settle(chefPage)

  // -----------------------------------------------------------------------
  // 7. Screenshot gallery showing all photos with featured badge visible
  // -----------------------------------------------------------------------
  await chefPage
    .locator('.chip', { hasText: 'Featured' })
    .first()
    .waitFor({ timeout: 10000 })
  await settle(chefPage)
  await screenshot(chefPage, 'gallery-with-featured-photo')
}
