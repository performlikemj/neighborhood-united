#!/usr/bin/env node
/**
 * Tutorial Screenshot Capture
 *
 * Walks through every chef workflow and captures named screenshots
 * suitable for tutorial / onboarding videos.
 *
 * Usage:
 *   # First reset ferris's data so screenshots show a clean journey
 *   python manage.py reset_chef_tutorial_data ferris --confirm
 *
 *   # Then capture screenshots (frontend + backend must be running)
 *   node frontend/scripts/tutorial-screenshots/capture.mjs
 *
 * Environment variables:
 *   E2E_BASE_URL      – frontend URL (default http://127.0.0.1:5174)
 *   E2E_BACKEND_URL   – backend URL  (default http://127.0.0.1:8000)
 *   HEADED            – set to "1" to run with visible browser
 *   WORKFLOW          – comma-separated workflow numbers to run, e.g. "01,03,05"
 */
import { resolve } from 'node:path'
import { mkdirSync } from 'node:fs'
import {
  baseUrl,
  credentials,
  viewport,
  login,
  ensureFrontendUp,
  ensureBackendUp,
  toastInitScript,
  createScreenshotter,
  openChefTab,
  waitForToast,
  resetToasts,
  settle,
  sampleImage,
  altImage,
} from './utils.mjs'

// Dynamic imports for workflow modules
const workflowModules = [
  { id: '01', mod: () => import('./workflows/01-onboarding.mjs') },
  { id: '02', mod: () => import('./workflows/02-profile-setup.mjs') },
  { id: '03', mod: () => import('./workflows/03-photo-gallery.mjs') },
  { id: '04', mod: () => import('./workflows/04-menu-builder.mjs') },
  { id: '05', mod: () => import('./workflows/05-services-pricing.mjs') },
  { id: '06', mod: () => import('./workflows/06-today-dashboard.mjs') },
  { id: '07', mod: () => import('./workflows/07-orders.mjs') },
  { id: '08', mod: () => import('./workflows/08-clients-crm.mjs') },
  { id: '09', mod: () => import('./workflows/09-prep-planning.mjs') },
  { id: '10', mod: () => import('./workflows/10-payment-links.mjs') },
  { id: '11', mod: () => import('./workflows/11-messaging.mjs') },
  { id: '12', mod: () => import('./workflows/12-insights.mjs') },
  { id: '13', mod: () => import('./workflows/13-sous-chef.mjs') },
]

if (!process.env.PLAYWRIGHT_BROWSERS_PATH) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = resolve(
    import.meta.dirname,
    '../../.playwright-browsers',
  )
}

const outputDir = resolve(import.meta.dirname, '../../tutorial_screenshots')

async function main() {
  console.log('=== Tutorial Screenshot Capture ===\n')

  // Determine which workflows to run
  const filterArg = process.env.WORKFLOW
  const filterIds = filterArg
    ? filterArg.split(',').map(s => s.trim().padStart(2, '0'))
    : null

  // Pre-flight
  console.log('[pre-flight] Checking services...')
  await ensureFrontendUp()
  console.log('  Frontend OK')
  await ensureBackendUp()
  console.log('  Backend OK\n')

  // Launch browser
  const { chromium } = await import('playwright')
  const headed = ['1', 'true', 'yes'].includes(
    String(process.env.HEADED || '').toLowerCase(),
  )
  const browser = await chromium.launch({ headless: !headed })

  // Mock Stripe payout status so all dashboard sections are accessible.
  // The real Stripe endpoint returns whether payouts are active, but in dev
  // environments Stripe is rarely configured.  Intercepting the API response
  // lets us show the full chef dashboard for tutorial screenshots.
  const mockStripeRoute = async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        has_account: true,
        is_active: true,
        needs_onboarding: false,
        account_id: 'acct_tutorial_mock',
        disabled_reason: null,
      }),
    })
  }

  // Chef context
  const chefContext = await browser.newContext({ viewport })
  await chefContext.addInitScript(toastInitScript)
  const chefPage = await chefContext.newPage()
  // Use regex so it matches URLs with query strings like ?user_id=87
  await chefPage.route(/meals\/api\/stripe-account-status\//, mockStripeRoute)
  chefPage.setDefaultTimeout(15000)

  // Customer context (for workflows that need a customer perspective)
  const customerContext = await browser.newContext({ viewport })
  await customerContext.addInitScript(toastInitScript)
  const customerPage = await customerContext.newPage()
  customerPage.setDefaultTimeout(15000)

  mkdirSync(outputDir, { recursive: true })

  // Login both users
  console.log('[auth] Logging in chef (ferris)...')
  await login(chefPage, credentials.chef, '/chefs/dashboard')
  await chefPage.goto(`${baseUrl}/chefs/dashboard`)
  await chefPage.waitForLoadState('networkidle')
  console.log('  Chef logged in\n')

  console.log('[auth] Logging in customer (kiho)...')
  await login(customerPage, credentials.customer, '/chefs')
  await customerPage.goto(`${baseUrl}/chefs`)
  await customerPage.waitForLoadState('networkidle')
  console.log('  Customer logged in\n')

  // Shared context passed to every workflow
  const ctx = {
    chefPage,
    customerPage,
    baseUrl,
    credentials,
    outputDir,
    openChefTab,
    waitForToast,
    resetToasts,
    settle,
    sampleImage,
    altImage,
    createScreenshotter,
  }

  // Workflows that require the Operations nav (only visible after onboarding
  // is fully complete).  Before the first of these runs we reload the
  // dashboard so React re-evaluates isOnboardingComplete with the data
  // created by earlier workflows (profile, photos, meals, services, payouts).
  const operationsWorkflows = new Set(['07', '08', '09', '11'])
  let didReloadForOperations = false

  // Execute workflows sequentially
  const results = []
  for (const entry of workflowModules) {
    if (filterIds && !filterIds.includes(entry.id)) {
      console.log(`[skip] Workflow ${entry.id} (filtered out)\n`)
      continue
    }

    // Reload dashboard before first Operations workflow so onboarding state refreshes
    if (operationsWorkflows.has(entry.id) && !didReloadForOperations) {
      console.log('[reload] Refreshing dashboard for Operations nav...')
      await chefPage.goto(`${baseUrl}/chefs/dashboard`)
      await chefPage.waitForLoadState('networkidle')
      await chefPage.waitForTimeout(1000)
      didReloadForOperations = true
      console.log('  Dashboard reloaded\n')
    }

    let mod
    try {
      mod = await entry.mod()
    } catch (err) {
      console.error(`[error] Failed to import workflow ${entry.id}: ${err.message}\n`)
      results.push({ id: entry.id, name: `workflow-${entry.id}`, status: 'import-error', error: err.message })
      continue
    }

    const { meta, default: capture } = mod
    const name = meta?.name || `workflow-${entry.id}`
    const dir = meta?.dir || `${entry.id}_unknown`

    console.log(`[workflow ${entry.id}] ${name}`)
    console.log(`  Output: ${dir}/`)

    try {
      const screenshot = createScreenshotter(outputDir, dir)
      await capture({ ...ctx, screenshot })
      console.log(`  Done.\n`)
      results.push({ id: entry.id, name, status: 'ok' })
    } catch (err) {
      console.error(`  FAILED: ${err.message}\n`)
      results.push({ id: entry.id, name, status: 'error', error: err.message })
    }
  }

  // Cleanup
  await chefContext.close()
  await customerContext.close()
  await browser.close()

  // Summary
  console.log('=== Summary ===')
  const ok = results.filter(r => r.status === 'ok').length
  const failed = results.filter(r => r.status !== 'ok').length
  console.log(`  Completed: ${ok}/${results.length}`)
  if (failed) {
    console.log(`  Failed: ${failed}`)
    for (const r of results.filter(r => r.status !== 'ok')) {
      console.log(`    - ${r.id} ${r.name}: ${r.error}`)
    }
  }
  console.log(`\nScreenshots saved to: ${outputDir}`)
}

main().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
