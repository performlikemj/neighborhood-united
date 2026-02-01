/**
 * Shared utilities for tutorial screenshot capture.
 * Reuses patterns from chefDashboardE2E.test.mjs.
 */
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

export const baseUrl = process.env.E2E_BASE_URL || 'http://127.0.0.1:5174'
export const backendUrl = process.env.E2E_BACKEND_URL || 'http://127.0.0.1:8000'

export const credentials = {
  chef: { username: 'ferris', password: 'Beihoo1228@!' },
  customer: { username: 'kiho', password: 'Beihoo1228@!' },
}

export const sampleImage = resolve(import.meta.dirname, '../../public/sautai_logo_new.png')
export const altImage = resolve(import.meta.dirname, '../../public/sautai_logo_web.png')

/** Default viewport for consistent tutorial screenshots. */
export const viewport = { width: 1440, height: 900 }

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function login(page, { username, password }, nextPath) {
  await page.goto(`${baseUrl}/login?next=${encodeURIComponent(nextPath)}`)
  await page.locator('#login-username').fill(username)
  await page.locator('#login-password').fill(password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

export async function openChefTab(page, label) {
  await page.locator('.chat-panel-overlay').waitFor({ state: 'detached' }).catch(() => {})
  await page.locator('.chef-nav').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})

  const normalizedLabel = (() => {
    if (label === 'Profile') return 'My Profile'
    if (label === 'Dashboard') return 'Today'
    return label
  })()

  // Expand sidebar if collapsed
  const expandBtn = page.getByRole('button', { name: /expand sidebar/i }).first()
  if (await expandBtn.isVisible().catch(() => false)) {
    await expandBtn.click().catch(() => {})
  }

  // Expand the correct nav section
  const sectionMap = {
    'Menu Builder': 'Your Menu',
    Services: 'Your Menu',
    Orders: 'Operations',
    Clients: 'Operations',
    'Prep Planning': 'Operations',
    Messages: 'Settings',
    'Payment Links': 'Settings',
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

  const navButton = page
    .locator('.chef-nav-item')
    .filter({ has: page.getByText(normalizedLabel, { exact: true }) })
    .first()
  await navButton.waitFor({ state: 'visible', timeout: 5000 })
  await navButton.scrollIntoViewIfNeeded().catch(() => {})
  await navButton.click()
  await page.waitForTimeout(400)
}

// ---------------------------------------------------------------------------
// Toast helpers
// ---------------------------------------------------------------------------

export async function waitForToast(page, text, timeout = 8000) {
  await page.waitForFunction(
    expected =>
      (window.__toastEvents || []).some(e => (e?.text || '').includes(expected)),
    text,
    { timeout },
  )
}

export async function resetToasts(page) {
  await page.evaluate(() => {
    window.__toastEvents = []
  })
}

/** Inject toast-tracking init script into a browser context. */
export function toastInitScript() {
  window.__toastEvents = []
  window.addEventListener('global-toast', e => {
    window.__toastEvents.push(e.detail || {})
  })
}

// ---------------------------------------------------------------------------
// Screenshot factory
// ---------------------------------------------------------------------------

/**
 * Create a screenshot helper bound to a specific workflow directory.
 *
 * @param {string} rootDir  – absolute path to the top-level output dir
 * @param {string} dirName  – subdirectory name, e.g. "01_onboarding"
 * @returns {Function} screenshot(page, name, opts?)
 */
export function createScreenshotter(rootDir, dirName) {
  const dir = resolve(rootDir, dirName)
  mkdirSync(dir, { recursive: true })
  let counter = 0

  return async function screenshot(page, name, opts = {}) {
    counter++
    const paddedNum = String(counter).padStart(2, '0')
    const safeName = name.replace(/[^a-z0-9-_]+/gi, '_').slice(0, 100)
    const filename = `${paddedNum}_${safeName}.png`
    const filePath = resolve(dir, filename)
    await page.screenshot({
      path: filePath,
      fullPage: opts.fullPage ?? true,
    })
    console.log(`    [screenshot] ${dirName}/${filename}`)
    return filePath
  }
}

// ---------------------------------------------------------------------------
// Connectivity checks
// ---------------------------------------------------------------------------

export async function ensureFrontendUp() {
  const res = await fetch(baseUrl, { method: 'GET' })
  if (!res.ok) throw new Error(`Frontend not reachable: ${res.status}`)
}

export async function ensureBackendUp() {
  const res = await fetch(`${backendUrl}/admin/`, { method: 'GET', redirect: 'manual' })
  if (!res.ok && res.status !== 302) throw new Error(`Backend not reachable: ${res.status}`)
}

// ---------------------------------------------------------------------------
// Misc helpers
// ---------------------------------------------------------------------------

/** Pause briefly so transitions / animations settle before screenshot. */
export async function settle(page, ms = 600) {
  await page.waitForTimeout(ms)
}
