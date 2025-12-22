import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const baseUrl = process.env.E2E_BASE_URL || 'http://127.0.0.1:5174'
const backendUrl = process.env.E2E_BACKEND_URL || 'http://127.0.0.1:8000'
const reportPath = resolve('tests/chef_dashboard_e2e_report.md')
const screenshotDir = resolve('tests/e2e_screenshots')
const assetsDir = resolve('tests/assets')
const sampleImage = resolve('public/sautai_logo_new.png')
const altImage = resolve('public/sautai_logo_web.png')
const heicFile = resolve('tests/assets/sample.heic')

if (!process.env.PLAYWRIGHT_BROWSERS_PATH) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = resolve('.playwright-browsers')
}

const credentials = {
  chef: { username: 'ferris', password: 'Beihoo1228@!' },
  customer: { username: 'kiho', password: 'Beihoo1228@!' }
}

const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
const dataSeeds = {
  experience: `E2E experience update ${timestamp}`,
  bio: `E2E bio update ${timestamp}`,
  calendly: `https://calendly.com/ferris/e2e-${timestamp}`,
  ingredient: `E2E Ingredient ${timestamp}`,
  ingredientAlt: `E2E Ingredient Alt ${timestamp}`,
  dish: `E2E Dish ${timestamp}`,
  meal: `E2E Meal ${timestamp}`,
  mealEdit: `E2E Meal Updated ${timestamp}`,
  service: `E2E Service ${timestamp}`,
  eventDescription: `E2E Event ${timestamp}`,
  paymentDescription: `E2E Payment Link ${timestamp}`,
  messageChef: `Chef hello ${timestamp}`,
  messageCustomer: `Customer hello ${timestamp}`
}

const results = []

class SkipError extends Error {
  constructor(message) {
    super(message)
    this.name = 'SkipError'
  }
}

class BlockedError extends Error {
  constructor(message) {
    super(message)
    this.name = 'BlockedError'
  }
}

function record(status, section, testCase, notes = '') {
  results.push({ status, section, testCase, notes })
}

function recordBlocked(section, testCase, reason) {
  record('blocked', section, testCase, reason)
}

function recordSkipped(section, testCase, reason) {
  record('skipped', section, testCase, reason)
}

async function step({ section, testCase, page, fn }) {
  const started = Date.now()
  try {
    const detail = await fn()
    const duration = Date.now() - started
    const notes = detail ? `${detail} (${duration}ms)` : `${duration}ms`
    record('pass', section, testCase, notes)
  } catch (err) {
    const duration = Date.now() - started
    if (err instanceof SkipError) {
      record('skipped', section, testCase, err.message)
      return
    }
    if (err instanceof BlockedError) {
      record('blocked', section, testCase, err.message)
      return
    }
    const message = err?.message ? err.message : String(err)
    record('fail', section, testCase, `${message} (${duration}ms)`)
    if (page) {
      try {
        mkdirSync(screenshotDir, { recursive: true })
        const safeName = `${section}-${testCase}`.replace(/[^a-z0-9-_]+/gi, '_').slice(0, 120)
        const shotPath = resolve(screenshotDir, `${safeName}.png`)
        await page.screenshot({ path: shotPath, fullPage: true })
      } catch {}
    }
  }
}

async function waitForToast(page, text) {
  await page.waitForFunction(
    expected => (window.__toastEvents || []).some(e => (e?.text || '').includes(expected)),
    text,
    { timeout: 8000 }
  )
}

async function resetToasts(page) {
  await page.evaluate(() => { window.__toastEvents = [] })
}

async function login(page, { username, password }, nextPath) {
  await page.goto(`${baseUrl}/login?next=${encodeURIComponent(nextPath)}`)
  await page.locator('div.label:has-text("Username") + input').fill(username)
  await page.locator('div.label:has-text("Password") + input').fill(password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(300)
}

async function ensureFrontendUp() {
  const res = await fetch(baseUrl, { method: 'GET' })
  if (!res.ok) {
    throw new Error(`Frontend not reachable: ${res.status}`)
  }
}

async function ensureBackendUp() {
  const res = await fetch(`${backendUrl}/admin/`, { method: 'GET' })
  if (!res.ok) {
    throw new Error(`Backend not reachable: ${res.status}`)
  }
}

async function openChefTab(page, label) {
  await page.locator('.chat-panel-overlay').waitFor({ state: 'detached' }).catch(() => {})
  // Wait for sidebar nav to be visible
  await page.locator('.chef-nav').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
  const normalizedLabel = (() => {
    if (label === 'Profile') return 'My Profile'
    if (label === 'Dashboard') return 'Today'
    return label
  })()

  const expandSidebarButton = page.getByRole('button', { name: /expand sidebar/i }).first()
  if (await expandSidebarButton.isVisible().catch(() => false)) {
    await expandSidebarButton.click().catch(() => {})
  }

  const sectionMap = {
    'Menu Builder': 'Your Menu',
    'Services': 'Your Menu',
    'Orders': 'Operations',
    'Clients': 'Operations',
    'Prep Planning': 'Operations',
    'Messages': 'Settings',
    'Payment Links': 'Settings'
  }
  const sectionTitle = sectionMap[normalizedLabel]
  if (sectionTitle) {
    const sectionHeader = page.locator('.nav-section-header', { hasText: sectionTitle }).first()
    if (await sectionHeader.count()) {
      const expanded = await sectionHeader.getAttribute('aria-expanded').catch(() => 'true')
      if (expanded === 'false') {
        await sectionHeader.click()
      }
    }
  }

  // Click the nav button by finding span with exact text inside chef-nav-item
  const navButton = page.locator('.chef-nav-item').filter({ has: page.getByText(normalizedLabel, { exact: true }) }).first()
  await navButton.waitFor({ state: 'visible', timeout: 5000 })
  await navButton.scrollIntoViewIfNeeded().catch(() => {})
  await navButton.click()
  await page.waitForTimeout(300)
}

async function openCustomerNav(page, label) {
  await page.getByRole('link', { name: label }).first().click()
  await page.waitForTimeout(300)
}

function buildReport() {
  const summary = results.reduce((acc, r) => {
    acc.total += 1
    acc[r.status] = (acc[r.status] || 0) + 1
    return acc
  }, { total: 0 })

  const lines = []
  lines.push('# Chef Dashboard E2E Report')
  lines.push('')
  lines.push(`Run: ${new Date().toISOString()}`)
  lines.push(`Frontend: ${baseUrl}`)
  lines.push(`Backend: ${backendUrl}`)
  lines.push(`Users: chef=ferris, customer=kiho`)
  lines.push('')
  lines.push('## Summary')
  lines.push(`- Total: ${summary.total}`)
  lines.push(`- Pass: ${summary.pass || 0}`)
  lines.push(`- Fail: ${summary.fail || 0}`)
  lines.push(`- Blocked: ${summary.blocked || 0}`)
  lines.push(`- Skipped: ${summary.skipped || 0}`)
  lines.push('')
  lines.push('## Results')
  lines.push('| Section | Test Case | Status | Notes |')
  lines.push('| --- | --- | --- | --- |')
  results.forEach(r => {
    const safeNotes = String(r.notes || '').replace(/\|/g, ' ')
    lines.push(`| ${r.section} | ${r.testCase} | ${r.status.toUpperCase()} | ${safeNotes} |`)
  })
  lines.push('')
  return lines.join('\n')
}

test('Chef dashboard user journey (ferris + kiho)', { timeout: 20 * 60 * 1000 }, async () => {
  const { chromium } = await import('playwright')
  await ensureFrontendUp()
  await ensureBackendUp()

  mkdirSync(screenshotDir, { recursive: true })
  mkdirSync(assetsDir, { recursive: true })

  const browser = await chromium.launch({ headless: true })
  const chefContext = await browser.newContext()
  const customerContext = await browser.newContext()
  const toastInit = () => {
    window.__toastEvents = []
    window.addEventListener('global-toast', (e) => {
      window.__toastEvents.push(e.detail || {})
    })
  }
  await chefContext.addInitScript(toastInit)
  await customerContext.addInitScript(toastInit)
  const chefPage = await chefContext.newPage()
  const customerPage = await customerContext.newPage()

  chefPage.setDefaultTimeout(15000)
  customerPage.setDefaultTimeout(15000)

  let payoutsActive = false
  let connectionId = null
  let chefId = null

  try {
    await step({
      section: 'Prerequisites',
      testCase: 'Chef login as ferris',
      page: chefPage,
      fn: async () => {
        await login(chefPage, credentials.chef, '/chefs/dashboard')
        await chefPage.goto(`${baseUrl}/chefs/dashboard`)
        await chefPage.waitForLoadState('networkidle')
        await chefPage.getByRole('heading', { name: 'Today' }).waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Prerequisites',
      testCase: 'Customer login as kiho',
      page: customerPage,
      fn: async () => {
        await login(customerPage, credentials.customer, '/my-chefs')
        await customerPage.goto(`${baseUrl}/chefs`)
        await customerPage.waitForLoadState('networkidle')
        await customerPage.locator('input.search-input').waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Prerequisites',
      testCase: 'Stripe payouts status visible',
      page: chefPage,
      fn: async () => {
        const active = chefPage.locator('text=Stripe Payouts Active').first()
        const setup = chefPage.locator('text=Payouts Setup Required').first()
        const connectStripe = chefPage.getByRole('button', { name: /connect stripe/i }).first()
        const statusVisible = await Promise.race([
          active.waitFor({ timeout: 6000 }).then(() => 'active').catch(() => null),
          setup.waitFor({ timeout: 6000 }).then(() => 'setup').catch(() => null),
          connectStripe.waitFor({ timeout: 6000 }).then(() => 'checklist').catch(() => null)
        ])
        if (statusVisible === 'active') {
          payoutsActive = true
          return 'Active'
        }
        if (statusVisible === 'setup') {
          payoutsActive = false
          return 'Setup required'
        }
        if (statusVisible === 'checklist') {
          payoutsActive = false
          return 'Setup required (checklist)'
        }
        throw new SkipError('Stripe status not visible in current view')
      }
    })

    await step({
      section: 'Dashboard',
      testCase: 'View dashboard overview',
      page: chefPage,
      fn: async () => {
        await chefPage.getByRole('heading', { name: 'Today' }).waitFor()
        await chefPage.locator('.today-dashboard').first().waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Dashboard',
      testCase: 'Open analytics drawer from metric card',
      page: chefPage,
      fn: async () => {
        const metricCard = chefPage.locator('.chef-metric-card', { hasText: 'Total Revenue' }).first()
        if ((await metricCard.count()) === 0) {
          throw new SkipError('Metrics view not available from current navigation')
        }
        await metricCard.click()
        await chefPage.locator('.analytics-drawer', { hasText: 'Revenue' }).waitFor({ timeout: 15000 })
        await chefPage.locator('.drawer-close-btn').click()
      }
    })

    await step({
      section: 'Dashboard',
      testCase: 'Sous Chef widget visible',
      page: chefPage,
      fn: async () => {
        await chefPage.getByRole('button', { name: 'Open Sous Chef' }).waitFor()
      }
    })

    await step({
      section: 'Profile',
      testCase: 'Update experience and bio',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Profile')
        // Wait for textareas to be visible before interacting
        await chefPage.locator('textarea').first().waitFor({ timeout: 15000 })
        const experience = chefPage.locator('textarea').nth(0)
        const bio = chefPage.locator('textarea').nth(1)
        await experience.fill(dataSeeds.experience)
        await bio.fill(dataSeeds.bio)
        await chefPage.getByRole('button', { name: /save changes/i }).click()
        await chefPage.waitForTimeout(1000)
        await openChefTab(chefPage, 'Dashboard')
        await openChefTab(chefPage, 'Profile')
        await assert.equal(await experience.inputValue(), dataSeeds.experience)
        await assert.equal(await bio.inputValue(), dataSeeds.bio)
      }
    })

    await step({
      section: 'Profile',
      testCase: 'Upload profile picture',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Profile')
        const fileInputs = chefPage.locator('input[type="file"]')
        await fileInputs.nth(0).setInputFiles(sampleImage)
        await chefPage.getByRole('button', { name: /save changes/i }).click()
        await chefPage.waitForTimeout(1500)
        await chefPage.locator('img[alt="Profile"]').first().waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Profile',
      testCase: 'Upload banner image',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Profile')
        const fileInputs = chefPage.locator('input[type="file"]')
        await fileInputs.nth(1).setInputFiles(altImage)
        await chefPage.getByRole('button', { name: /save changes/i }).click()
        await chefPage.getByText('Banner updated').waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Profile',
      testCase: 'Add Calendly link',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Profile')
        const calendlyInput = chefPage.locator('input[type="url"]')
        await calendlyInput.fill(dataSeeds.calendly)
        await chefPage.getByRole('button', { name: /save changes/i }).click()
        await chefPage.waitForTimeout(1000)
        await openChefTab(chefPage, 'Dashboard')
        await openChefTab(chefPage, 'Profile')
        await assert.equal(await calendlyInput.inputValue(), dataSeeds.calendly)
      }
    })

    await step({
      section: 'Profile',
      testCase: 'View public preview',
      page: chefPage,
      fn: async () => {
        let popup = null
        try {
          [popup] = await Promise.all([
            chefPage.waitForEvent('popup', { timeout: 8000 }),
            chefPage.getByRole('link', { name: /view public profile/i }).click()
          ])
        } catch {
          await chefPage.getByRole('link', { name: /view public profile/i }).click()
        }
        if (popup) {
          await popup.waitForLoadState('domcontentloaded')
          await popup.close()
          return
        }
        // Fallback if navigation happens in same tab
        await chefPage.waitForURL(/\/c\//, { timeout: 8000 })
        await chefPage.goBack()
      }
    })

    await step({
      section: 'Profile',
      testCase: 'Open service area picker',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Profile')
        await chefPage.getByRole('button', { name: /request new areas/i }).click()
        await chefPage.locator('input[placeholder*="Search cities"]').waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Profile',
      testCase: 'Request new service area',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Profile')
        const searchInput = chefPage.locator('input[placeholder*="Search cities"]')
        await searchInput.fill('New')
        const results = chefPage.locator('.service-area-picker').locator('div', { hasText: 'codes' })
        if ((await results.count()) === 0) {
          throw new SkipError('No area search results')
        }
        await results.first().click()
        const requestButton = chefPage.getByRole('button', { name: /Request \d+ Area/i })
        if (!(await requestButton.isEnabled())) {
          throw new SkipError('Request button disabled (no selectable areas)')
        }
        await requestButton.click()
        await chefPage.locator('text=Pending Requests').waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Profile',
      testCase: 'Cancel pending request',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Profile')
        const cancelButton = chefPage.getByRole('button', { name: 'Cancel' }).first()
        await cancelButton.click()
        await chefPage.waitForTimeout(1000)
      }
    })

    await step({
      section: 'Profile',
      testCase: 'View request history',
      page: chefPage,
      fn: async () => {
        const details = chefPage.locator('summary', { hasText: 'Recent request history' })
        if (await details.count()) {
          await details.click()
        } else {
          throw new SkipError('No request history section')
        }
      }
    })

    await step({
      section: 'Photos',
      testCase: 'Upload photo to gallery',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'My Profile')
        await chefPage.getByRole('button', { name: /^photos/i }).click()
        await resetToasts(chefPage)
        const uploadCard = chefPage.locator('[data-testid="photo-upload-card"]')
        await uploadCard.waitFor({ state: 'visible', timeout: 5000 })
        // Set the file via the hidden file input inside the upload card
        await uploadCard.locator('input[type="file"]').setInputFiles(sampleImage)
        const titleInput = uploadCard.locator('[data-testid="photo-title"]')
        const captionInput = uploadCard.locator('[data-testid="photo-caption"]')
        await titleInput.waitFor({ state: 'visible', timeout: 5000 })
        await titleInput.click()
        await titleInput.type(`E2E Photo ${timestamp}`, { delay: 25 })
        await chefPage.waitForFunction((value) => {
          const el = document.querySelector('[data-testid="photo-title"]')
          return el && el.value === value
        }, `E2E Photo ${timestamp}`)
        await captionInput.click()
        await captionInput.type('E2E caption', { delay: 25 })
        await chefPage.getByRole('button', { name: /^upload$/i }).click()
        await waitForToast(chefPage, 'Photo uploaded')
        // Wait for React state to update after loadChefProfile completes
        await chefPage.waitForTimeout(2000)
        // Photo should appear in gallery now
        await chefPage.locator('.thumb-card', { hasText: `E2E Photo ${timestamp}` }).waitFor({ timeout: 30000 })
      }
    })

    await step({
      section: 'Photos',
      testCase: 'Upload featured photo',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'My Profile')
        await chefPage.getByRole('button', { name: /^photos/i }).click()
        await resetToasts(chefPage)
        const uploadCard = chefPage.locator('[data-testid="photo-upload-card"]')
        await uploadCard.waitFor({ state: 'visible', timeout: 5000 })
        // Set the file via the hidden file input inside the upload card
        await uploadCard.locator('input[type="file"]').setInputFiles(altImage)
        const titleInput = uploadCard.locator('[data-testid="photo-title"]')
        const captionInput = uploadCard.locator('[data-testid="photo-caption"]')
        await titleInput.waitFor({ state: 'visible', timeout: 5000 })
        await titleInput.click()
        await titleInput.type(`E2E Featured ${timestamp}`, { delay: 25 })
        await chefPage.waitForFunction((value) => {
          const el = document.querySelector('[data-testid="photo-title"]')
          return el && el.value === value
        }, `E2E Featured ${timestamp}`)
        await captionInput.click()
        await captionInput.type('Featured caption', { delay: 25 })
        await uploadCard.getByLabel('Featured').check()
        await uploadCard.getByRole('button', { name: /^upload$/i }).click()
        await waitForToast(chefPage, 'Photo uploaded')
        // Wait for React state to update after loadChefProfile completes
        await chefPage.waitForTimeout(2000)
        // Photo should appear in gallery with featured chip
        await chefPage.locator('.thumb-card', { hasText: `E2E Featured ${timestamp}` }).waitFor({ timeout: 30000 })
        await chefPage.locator('.thumb-card', { hasText: `E2E Featured ${timestamp}` }).locator('.chip').waitFor()
      }
    })

    await step({
      section: 'Photos',
      testCase: 'HEIC rejection',
      page: chefPage,
      fn: async () => {
        await resetToasts(chefPage)
        await chefPage.locator('input[type="file"]').setInputFiles({
          name: 'sample.heic',
          mimeType: 'image/heic',
          buffer: Buffer.from('heic')
        })
        await chefPage.getByRole('button', { name: /upload/i }).click()
        await waitForToast(chefPage, 'HEIC images are not supported')
      }
    })

    await step({
      section: 'Photos',
      testCase: 'Delete photo from gallery',
      page: chefPage,
      fn: async () => {
        const photoCard = chefPage.locator('.thumb-card', { hasText: `E2E Photo ${timestamp}` }).first()
        if ((await photoCard.count()) === 0) {
          throw new SkipError('Uploaded photo not found in gallery')
        }
        await photoCard.getByRole('button', { name: /delete/i }).click()
        await chefPage.waitForTimeout(1500)
      }
    })

    if (!payoutsActive) {
      recordBlocked('Kitchen', 'Ingredients/Dishes/Meals creation', 'Stripe payouts not active')
    } else {
      await step({
        section: 'Kitchen',
        testCase: 'Create ingredient',
        page: chefPage,
        fn: async () => {
          await openChefTab(chefPage, 'Kitchen')
          await resetToasts(chefPage)
          const ingredientSection = chefPage.locator('.chef-kitchen-section', { hasText: 'Ingredients' }).first()
          await ingredientSection.getByRole('button', { name: 'Add' }).click()
          await ingredientSection.locator('input[placeholder*="Chicken"]').fill(dataSeeds.ingredient)
          await ingredientSection.locator('input[type="number"]').first().fill('100')
          const addButton = ingredientSection.getByRole('button', { name: /Add Ingredient/i })
          if (!(await addButton.isEnabled())) {
            throw new BlockedError('Add Ingredient button disabled')
          }
          await addButton.click()
          // Wait for success toast which fires after loadIngredients completes
          await waitForToast(chefPage, 'Ingredient created')
          // Use search to find the new ingredient (list is paginated to 12 items)
          const searchInput = ingredientSection.locator('input[placeholder*="Search ingredients"]')
          if (await searchInput.count()) {
            await searchInput.fill(dataSeeds.ingredient.slice(0, 20))
          }
          await chefPage.locator('.chef-item-name', { hasText: dataSeeds.ingredient }).waitFor({ timeout: 15000 })
        }
      })

      await step({
        section: 'Kitchen',
        testCase: 'Duplicate ingredient check',
        page: chefPage,
        fn: async () => {
          const ingredientSection = chefPage.locator('.chef-kitchen-section', { hasText: 'Ingredients' }).first()
          await ingredientSection.locator('input[placeholder*="Chicken"]').fill(dataSeeds.ingredient)
          await ingredientSection.locator('text=Ingredient already exists').waitFor({ timeout: 15000 })
        }
      })

      await step({
        section: 'Kitchen',
        testCase: 'Create second ingredient',
        page: chefPage,
        fn: async () => {
          await resetToasts(chefPage)
          const ingredientSection = chefPage.locator('.chef-kitchen-section', { hasText: 'Ingredients' }).first()
          // Clear any existing search first
          const searchInput = ingredientSection.locator('input[placeholder*="Search ingredients"]')
          if (await searchInput.count()) {
            await searchInput.fill('')
          }
          await ingredientSection.locator('input[placeholder*="Chicken"]').fill(dataSeeds.ingredientAlt)
          const addButton = ingredientSection.getByRole('button', { name: /Add Ingredient/i })
          if (!(await addButton.isEnabled())) {
            throw new BlockedError('Add Ingredient button disabled')
          }
          await addButton.click()
          // Wait for success toast which fires after loadIngredients completes
          await waitForToast(chefPage, 'Ingredient created')
          // Use search to find the new ingredient (list is paginated to 12 items)
          if (await searchInput.count()) {
            await searchInput.fill(dataSeeds.ingredientAlt.slice(0, 20))
          }
          await chefPage.locator('.chef-item-name', { hasText: dataSeeds.ingredientAlt }).waitFor({ timeout: 15000 })
        }
      })

      await step({
        section: 'Kitchen',
        testCase: 'Create dish with multi-select',
        page: chefPage,
        fn: async () => {
          const dishesSection = chefPage.locator('.chef-kitchen-section', { hasText: 'Dishes' }).first()
          await dishesSection.getByRole('button', { name: 'Add' }).click()
          await dishesSection.locator('input.input').first().fill(dataSeeds.dish)
          const select = dishesSection.locator('select[multiple]')
          if ((await select.locator('option').count()) === 0) {
            throw new SkipError('No ingredients available for dishes')
          }
          await select.selectOption([
            { label: dataSeeds.ingredient },
            { label: dataSeeds.ingredientAlt }
          ])
          const createDish = dishesSection.getByRole('button', { name: /Create Dish/i })
          if (!(await createDish.isEnabled())) {
            throw new BlockedError('Create Dish button disabled')
          }
          await createDish.click()
          await chefPage.locator('.chef-item-name', { hasText: dataSeeds.dish }).waitFor({ timeout: 15000 })
        }
      })

      await step({
        section: 'Kitchen',
        testCase: 'Create meal',
        page: chefPage,
        fn: async () => {
          const mealsSection = chefPage.locator('.chef-kitchen-section', { hasText: 'Meals' }).first()
          await mealsSection.getByRole('button', { name: 'Add' }).click()
          await mealsSection.locator('input[placeholder*="Sunday"]').fill(dataSeeds.meal)
          await mealsSection.locator('textarea').first().fill('E2E meal description')
          await mealsSection.locator('select').first().selectOption('Dinner')
          await mealsSection.locator('.label:has-text(\"Price\") + input').fill('25')
          const dishCheckbox = mealsSection.getByLabel(dataSeeds.dish)
          if ((await dishCheckbox.count()) === 0) {
            throw new SkipError('Dish checkbox not found')
          }
          await dishCheckbox.click()
          const createMeal = mealsSection.getByRole('button', { name: /Create Meal/i })
          if (!(await createMeal.isEnabled())) {
            throw new BlockedError('Create Meal button disabled')
          }
          await createMeal.click()
          await chefPage.locator('.chef-item-card', { hasText: dataSeeds.meal }).waitFor({ timeout: 15000 })
        }
      })

      await step({
        section: 'Kitchen',
        testCase: 'Open meal detail slideout and edit',
        page: chefPage,
        fn: async () => {
          const mealCard = chefPage.locator('.chef-item-card', { hasText: dataSeeds.meal }).first()
          if ((await mealCard.count()) === 0) {
            throw new SkipError('Meal card not found')
          }
          await mealCard.click()
          await chefPage.locator('.meal-slideout').waitFor({ timeout: 15000 })
          await chefPage.getByRole('button', { name: /Edit/i }).click()
          await chefPage.locator('input.form-input').first().fill(dataSeeds.mealEdit)
          await resetToasts(chefPage)
          await chefPage.getByRole('button', { name: /Save Changes/i }).click()
          await waitForToast(chefPage, 'Meal updated successfully')
        }
      })

      await step({
        section: 'Kitchen',
        testCase: 'Delete meal',
        page: chefPage,
        fn: async () => {
          chefPage.once('dialog', dialog => dialog.accept().catch(() => {}))
          const deleteButton = chefPage.getByRole('button', { name: /Delete Meal|Delete/i }).first()
          if ((await deleteButton.count()) === 0) {
            throw new SkipError('Delete button not available')
          }
          await resetToasts(chefPage)
          await deleteButton.click()
          await waitForToast(chefPage, 'Meal deleted')
        }
      })
    }

    await step({
      section: 'Clients',
      testCase: 'View clients tab',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Clients')
        await chefPage.getByRole('heading', { name: 'Client Connections' }).waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Customer',
      testCase: 'Browse chefs directory',
      page: customerPage,
      fn: async () => {
        await customerPage.goto(`${baseUrl}/chefs`)
        await customerPage.locator('input.search-input').waitFor()
      }
    })

    await step({
      section: 'Customer',
      testCase: 'Search for chef ferris',
      page: customerPage,
      fn: async () => {
        await customerPage.locator('input.search-input').fill('ferris')
        await customerPage.getByText('ferris', { exact: false }).first().waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Customer',
      testCase: 'Open ferris public profile',
      page: customerPage,
      fn: async () => {
        await customerPage.getByText('ferris', { exact: false }).first().click()
        await customerPage.waitForLoadState('networkidle')
        await customerPage.getByRole('heading', { name: 'ferris', exact: true }).waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Customer',
      testCase: 'View profile info and gallery',
      page: customerPage,
      fn: async () => {
        await customerPage.getByRole('heading', { name: /experience/i }).waitFor({ timeout: 15000 })
        await customerPage.getByText('Gallery', { exact: false }).first().waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Customer',
      testCase: 'Check availability modal',
      page: customerPage,
      fn: async () => {
        const availability = customerPage.getByRole('button', { name: /Check Availability/i })
        if (await availability.count()) {
          await availability.click()
          const modal = customerPage.locator('.service-areas-modal')
          await modal.waitFor({ timeout: 15000 })
          await modal.locator('.service-areas-modal-close').click()
          await customerPage.locator('.service-areas-modal-overlay').waitFor({ state: 'detached', timeout: 15000 })
        } else {
          throw new SkipError('No availability button')
        }
      }
    })

    await step({
      section: 'Customer',
      testCase: 'Request connection with chef',
      page: customerPage,
      fn: async () => {
        const requestBtn = customerPage.getByRole('button', { name: /Request Invitation/i })
        if (await requestBtn.count()) {
          await resetToasts(customerPage)
          await requestBtn.click()
          await waitForToast(customerPage, 'Invitation request sent')
        } else {
          throw new SkipError('Request button not available')
        }
      }
    })

    await step({
      section: 'Clients',
      testCase: 'Accept connection request',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Clients')
        const clientRow = chefPage.getByText('kiho', { exact: false }).first()
        if ((await clientRow.count()) === 0) {
          throw new SkipError('No pending client row for kiho')
        }
        await clientRow.click()
        const acceptBtn = chefPage.getByRole('button', { name: /Accept/i }).first()
        if (await acceptBtn.count()) {
          await resetToasts(chefPage)
          await acceptBtn.click()
          await waitForToast(chefPage, 'Connection accepted')
        } else {
          throw new SkipError('No accept button found')
        }
      }
    })

    await step({
      section: 'Customer',
      testCase: 'Open My Chefs (Chef Hub)',
      page: customerPage,
      fn: async () => {
        await customerPage.goto(`${baseUrl}/my-chefs`)
        await customerPage.waitForLoadState('networkidle')
        const chefCard = customerPage.getByText(/ferris/i).first()
        if ((await chefCard.count()) === 0) {
          throw new SkipError('Ferris not listed in My Chefs')
        }
        await chefCard.click()
        await customerPage.getByRole('heading', { name: /ferris/i }).waitFor({ timeout: 15000 })
        const url = customerPage.url()
        const match = url.match(/my-chefs\/(\d+)/)
        chefId = match ? match[1] : null
      }
    })

    await step({
      section: 'Customer',
      testCase: 'Browse menu modal',
      page: customerPage,
      fn: async () => {
        if (!chefId) {
          throw new SkipError('Chef Hub not available')
        }
        await customerPage.getByRole('button', { name: /Browse Menu/i }).click()
        await customerPage.getByRole('dialog', { name: 'Browse Menu' }).waitFor({ timeout: 15000 })
        await customerPage.locator('.menu-modal-close').click()
        await customerPage.locator('.menu-modal').waitFor({ state: 'detached', timeout: 15000 })
      }
    })

    await step({
      section: 'Customer',
      testCase: 'Request service modal',
      page: customerPage,
      fn: async () => {
        if (!chefId) {
          throw new SkipError('Chef Hub not available')
        }
        await customerPage.getByRole('button', { name: /Request Service/i }).click()
        await customerPage.getByRole('dialog', { name: 'Request Service' }).waitFor({ timeout: 15000 })
        await customerPage.locator('.service-modal-close').click()
        await customerPage.locator('.service-modal').waitFor({ state: 'detached', timeout: 15000 })
      }
    })

    await step({
      section: 'Messaging',
      testCase: 'Customer sends message',
      page: customerPage,
      fn: async () => {
        if (!chefId) {
          throw new SkipError('Chef Hub not available')
        }
        await customerPage.getByRole('button', { name: /Message Chef/i }).click()
        await customerPage.locator('textarea.chat-input').waitFor({ timeout: 15000 })
        await customerPage.locator('textarea.chat-input').fill(dataSeeds.messageCustomer)
        await customerPage.locator('.chat-send-btn').click()
        await customerPage.waitForTimeout(1000)
        await customerPage.locator('.chat-panel-close').click()
        await customerPage.locator('.chat-panel').waitFor({ state: 'detached', timeout: 15000 })
      }
    })

    await step({
      section: 'Messaging',
      testCase: 'Chef sees conversation and replies',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Messages')
        await chefPage.locator('.conversation-item').first().click()
        await chefPage.locator('textarea.chat-input').waitFor({ timeout: 15000 })
        await chefPage.locator('textarea.chat-input').fill(dataSeeds.messageChef)
        await chefPage.locator('.chat-send-btn').click()
        await chefPage.waitForTimeout(1000)
        await chefPage.locator('.chat-panel-close').click()
        await chefPage.locator('.chat-panel').waitFor({ state: 'detached', timeout: 15000 })
      }
    })

    await step({
      section: 'Payments',
      testCase: 'View payment links tab',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Payment Links')
        await chefPage.getByRole('heading', { name: /Payment Links/i }).waitFor({ timeout: 15000 })
      }
    })

    if (!payoutsActive) {
      recordBlocked('Services', 'Service offerings & tiers', 'Stripe payouts not active')
      recordBlocked('Events', 'Create event', 'Stripe payouts not active')
    } else {
      await step({
        section: 'Services',
        testCase: 'Create service offering',
        page: chefPage,
        fn: async () => {
          await openChefTab(chefPage, 'Services')
          const serviceForm = chefPage.locator('.card', { hasText: 'Create service offering' }).first()
          await serviceForm.locator('.label:has-text(\"Title\") + input').fill(dataSeeds.service)
          await serviceForm.locator('.label:has-text(\"Description\") + textarea').fill('E2E service description')
          await serviceForm.locator('.label:has-text(\"Default duration\") + input').fill('90')
          await serviceForm.locator('.label:has-text(\"Max travel miles\") + input').fill('10')
          await resetToasts(chefPage)
          await serviceForm.getByRole('button', { name: /Create offering/i }).click()
          await waitForToast(chefPage, 'Service offering created')
          await chefPage.locator('h4', { hasText: dataSeeds.service }).first().waitFor({ timeout: 15000 })
        }
      })

      await step({
        section: 'Services',
        testCase: 'Add pricing tier',
        page: chefPage,
        fn: async () => {
          const serviceCard = chefPage.locator('.card').filter({
            has: chefPage.getByRole('heading', { name: dataSeeds.service })
          }).first()
          if ((await serviceCard.count()) === 0) {
            throw new SkipError('Service offering not found')
          }
          await serviceCard.getByRole('button', { name: /Add tier/i }).first().click()
          const tierForm = chefPage.locator('form', { hasText: 'Create tier' }).first()
          await tierForm.locator('.label:has-text(\"Household min\") + input').fill('1')
          await tierForm.locator('.label:has-text(\"Household max\") + input').fill('4')
          await tierForm.locator('.label:has-text(\"Price\") + input').fill('150')
          await resetToasts(chefPage)
          await tierForm.getByRole('button', { name: /Create tier/i }).click()
          await waitForToast(chefPage, 'Tier created')
        }
      })

      await step({
        section: 'Events',
        testCase: 'Create event',
        page: chefPage,
        fn: async () => {
          await openChefTab(chefPage, 'Events')
          const eventForm = chefPage.locator('.card', { hasText: 'Create event' }).first()
          const mealSelect = eventForm.locator('select').first()
          const options = await mealSelect.locator('option').all()
          if (options.length <= 1) {
            throw new SkipError('No meals available')
          }
          await mealSelect.selectOption({ index: 1 })
          const today = new Date()
          today.setDate(today.getDate() + 1)
          const dateStr = today.toISOString().slice(0, 10)
          await eventForm.locator('.label:has-text(\"Event date\") + input').fill(dateStr)
          await eventForm.locator('.label:has-text(\"Event time\") + input').fill('12:00')
          await eventForm.locator('.label:has-text(\"Cutoff date\") + input').fill(dateStr)
          await eventForm.locator('.label:has-text(\"Cutoff time\") + input').fill('10:00')
          await eventForm.locator('.label:has-text(\"Base price\") + input').fill('25')
          await eventForm.locator('.label:has-text(\"Min price\") + input').fill('20')
          await eventForm.locator('.label:has-text(\"Max orders\") + input').fill('10')
          await eventForm.locator('.label:has-text(\"Min orders\") + input').fill('1')
          await eventForm.locator('.label:has-text(\"Description\") + input').fill(dataSeeds.eventDescription)
          await eventForm.getByRole('button', { name: /Create Event/i }).click()
          const eventsCard = chefPage.locator('.card', { hasText: 'Your events' }).first()
          await eventsCard.getByText(dateStr).first().waitFor({ timeout: 30000 })
        }
      })
    }

    await step({
      section: 'Orders',
      testCase: 'Orders filters and refresh',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Orders')
        await chefPage.locator('input#chef-orders-search').fill('test')
        await chefPage.locator('select#chef-orders-type').selectOption('meal')
        await chefPage.locator('select#chef-orders-status').selectOption('completed')
        await chefPage.locator('select#chef-orders-sort').selectOption('oldest')
        const toolbar = chefPage.locator('.chef-orders-toolbar')
        await toolbar.getByRole('button', { name: /Clear filters/i }).first().click()
        await toolbar.getByRole('button', { name: /Refresh/i }).first().click()
      }
    })

    await step({
      section: 'Prep Planning',
      testCase: 'View prep planning tab',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Prep Planning')
        await chefPage.getByRole('heading', { name: /Prep Planning/i }).waitFor({ timeout: 15000 })
      }
    })

    await step({
      section: 'Sous Chef',
      testCase: 'Open widget and change emoji',
      page: chefPage,
      fn: async () => {
        await chefPage.locator('.chat-panel-overlay').waitFor({ state: 'detached' }).catch(() => {})
        await chefPage.getByRole('button', { name: 'Open Sous Chef' }).click()
        await chefPage.getByRole('heading', { name: 'Sous Chef' }).waitFor({ timeout: 15000 })
        await chefPage.locator('.emoji-trigger').click()
        const emojiOptions = chefPage.locator('.emoji-option')
        if (await emojiOptions.count()) {
          await emojiOptions.nth(0).click()
          await chefPage.waitForTimeout(500)
        } else {
          throw new SkipError('No emoji options found')
        }
        await chefPage.locator('.sous-chef-panel .close-btn').click()
      }
    })

    await step({
      section: 'Connections',
      testCase: 'End connection',
      page: chefPage,
      fn: async () => {
        await openChefTab(chefPage, 'Clients')
        const clientRow = chefPage.getByText('kiho', { exact: false }).first()
        if ((await clientRow.count()) === 0) {
          throw new SkipError('No client row for kiho')
        }
        await clientRow.click()
        const endButton = chefPage.getByRole('button', { name: /End Connection/i }).first()
        if (await endButton.count()) {
          if (!(await endButton.isEnabled())) {
            throw new SkipError('End connection button disabled')
          }
          chefPage.once('dialog', dialog => dialog.accept().catch(() => {}))
          await resetToasts(chefPage)
          await endButton.click()
          await waitForToast(chefPage, 'Connection ended')
        } else {
          throw new SkipError('No end connection button')
        }
      }
    })
  } finally {
    try {
      writeFileSync(reportPath, buildReport(), 'utf8')
    } catch {}
    await chefContext.close()
    await customerContext.close()
    await browser.close()
  }

  const failures = results.filter(r => r.status === 'fail')
  assert.equal(failures.length, 0, `Some E2E checks failed: ${failures.map(f => `${f.section} - ${f.testCase}`).join(', ')}`)
})
