/**
 * TelegramSettings Component Tests
 *
 * Structural tests for Telegram integration React components.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Component paths
const settingsPath = resolve('src/components/telegram/TelegramSettings.jsx')
const connectPath = resolve('src/components/telegram/TelegramConnect.jsx')
const connectedPath = resolve('src/components/telegram/TelegramConnected.jsx')
const indexPath = resolve('src/components/telegram/index.js')

// API/Hook paths
const clientPath = resolve('src/api/telegramClient.js')
const hookPath = resolve('src/hooks/useTelegram.js')

function loadFile(path) {
  assert.ok(existsSync(path), `Expected ${path} to exist`)
  return readFileSync(path, 'utf8')
}

// ==========================================
// TelegramSettings Component Tests
// ==========================================

test('TelegramSettings component exists and exports properly', () => {
  const source = loadFile(settingsPath)
  
  assert.match(
    source,
    /export\s+default\s+function\s+TelegramSettings/,
    'Should export TelegramSettings as default'
  )
  
  assert.match(
    source,
    /import.*TelegramConnect.*from.*TelegramConnect/,
    'Should import TelegramConnect component'
  )
  
  assert.match(
    source,
    /import.*TelegramConnected.*from.*TelegramConnected/,
    'Should import TelegramConnected component'
  )
})

test('TelegramSettings uses useTelegramStatus hook', () => {
  const source = loadFile(settingsPath)
  
  assert.match(
    source,
    /useTelegramStatus/,
    'Should use useTelegramStatus hook'
  )
})

test('TelegramSettings shows loading state', () => {
  const source = loadFile(settingsPath)
  
  assert.match(
    source,
    /isLoading/,
    'Should handle loading state'
  )
  
  assert.match(
    source,
    /Loading.*Telegram/i,
    'Should show loading message'
  )
})

test('TelegramSettings shows error state', () => {
  const source = loadFile(settingsPath)
  
  assert.match(
    source,
    /error/i,
    'Should handle error state'
  )
  
  assert.match(
    source,
    /Failed.*load/i,
    'Should show error message'
  )
})

test('TelegramSettings conditionally renders Connect or Connected', () => {
  const source = loadFile(settingsPath)
  
  assert.match(
    source,
    /status\?\.linked\s*\?/,
    'Should conditionally render based on linked status'
  )
  
  assert.match(
    source,
    /<TelegramConnect/,
    'Should render TelegramConnect when not linked'
  )
  
  assert.match(
    source,
    /<TelegramConnected/,
    'Should render TelegramConnected when linked'
  )
})

// ==========================================
// TelegramConnect Component Tests
// ==========================================

test('TelegramConnect component structure', () => {
  const source = loadFile(connectPath)
  
  assert.match(
    source,
    /export\s+default\s+function\s+TelegramConnect/,
    'Should export TelegramConnect as default'
  )
})

test('TelegramConnect shows generate button initially', () => {
  const source = loadFile(connectPath)
  
  assert.match(
    source,
    /Connect\s+Telegram/i,
    'Should show Connect Telegram button text'
  )
  
  assert.match(
    source,
    /onClick.*handleGenerate/,
    'Should have click handler to generate link'
  )
})

test('TelegramConnect displays QR code', () => {
  const source = loadFile(connectPath)
  
  assert.match(
    source,
    /import.*QRCodeSVG.*from.*qrcode\.react/,
    'Should import QRCodeSVG from qrcode.react'
  )
  
  assert.match(
    source,
    /<QRCodeSVG/,
    'Should render QRCodeSVG component'
  )
})

test('TelegramConnect shows deep link button', () => {
  const source = loadFile(connectPath)
  
  assert.match(
    source,
    /Open\s+in\s+Telegram/i,
    'Should show deep link button text'
  )
  
  assert.match(
    source,
    /href=\{linkData\.deep_link\}/,
    'Should use deep_link from API'
  )
})

test('TelegramConnect shows expiration warning', () => {
  const source = loadFile(connectPath)
  
  assert.match(
    source,
    /expires/i,
    'Should mention link expiration'
  )
  
  assert.match(
    source,
    /timeRemaining/,
    'Should track time remaining'
  )
})

test('TelegramConnect handles expired state', () => {
  const source = loadFile(connectPath)
  
  assert.match(
    source,
    /isExpired/,
    'Should track expired state'
  )
  
  assert.match(
    source,
    /Link\s+expired/i,
    'Should show expired message'
  )
  
  assert.match(
    source,
    /Generate\s+New\s+Link/i,
    'Should allow regenerating expired link'
  )
})

test('TelegramConnect polls for connection status', () => {
  const source = loadFile(connectPath)
  
  assert.match(
    source,
    /useEffect.*invalidateStatus.*setInterval/s,
    'Should poll for status updates via useEffect'
  )
})

// ==========================================
// TelegramConnected Component Tests
// ==========================================

test('TelegramConnected component structure', () => {
  const source = loadFile(connectedPath)
  
  assert.match(
    source,
    /export\s+default\s+function\s+TelegramConnected/,
    'Should export TelegramConnected as default'
  )
})

test('TelegramConnected shows connected status', () => {
  const source = loadFile(connectedPath)
  
  assert.match(
    source,
    /Connected/i,
    'Should show connected status'
  )
  
  assert.match(
    source,
    /telegram_username|displayName/,
    'Should display username'
  )
})

test('TelegramConnected has notification toggles', () => {
  const source = loadFile(connectedPath)
  
  const notificationSettings = [
    'notify_new_orders',
    'notify_order_updates',
    'notify_schedule_reminders',
    'notify_customer_messages'
  ]
  
  notificationSettings.forEach(setting => {
    assert.match(
      source,
      new RegExp(setting),
      `Should have toggle for ${setting}`
    )
  })
})

test('TelegramConnected has quiet hours settings', () => {
  const source = loadFile(connectedPath)
  
  assert.match(
    source,
    /quiet_hours_enabled/,
    'Should have quiet hours toggle'
  )
  
  assert.match(
    source,
    /quiet_hours_start/,
    'Should have quiet hours start time'
  )
  
  assert.match(
    source,
    /quiet_hours_end/,
    'Should have quiet hours end time'
  )
  
  assert.match(
    source,
    /type="time"/,
    'Should have time inputs'
  )
})

test('TelegramConnected has disconnect button with confirmation', () => {
  const source = loadFile(connectedPath)
  
  assert.match(
    source,
    /Disconnect\s+Telegram/i,
    'Should have disconnect button'
  )
  
  assert.match(
    source,
    /showDisconnectConfirm/,
    'Should track confirmation state'
  )
  
  assert.match(
    source,
    /Are\s+you\s+sure/i,
    'Should show confirmation message'
  )
})

test('TelegramConnected uses update settings mutation', () => {
  const source = loadFile(connectedPath)
  
  assert.match(
    source,
    /useUpdateTelegramSettings/,
    'Should use useUpdateTelegramSettings hook'
  )
  
  assert.match(
    source,
    /updateSettingsMutation\.mutate/,
    'Should call mutate on settings change'
  )
})

// ==========================================
// API Client Tests
// ==========================================

test('telegramClient exports all required functions', () => {
  const source = loadFile(clientPath)
  
  const requiredFunctions = [
    'getTelegramStatus',
    'generateTelegramLink',
    'unlinkTelegram',
    'updateTelegramSettings'
  ]
  
  requiredFunctions.forEach(fn => {
    assert.match(
      source,
      new RegExp(`export\\s+(async\\s+)?function\\s+${fn}`),
      `Should export ${fn} function`
    )
  })
})

test('telegramClient uses correct API endpoints', () => {
  const source = loadFile(clientPath)
  
  // Check base URL is defined
  assert.match(
    source,
    /TELEGRAM_BASE\s*=\s*['"`]\/chefs\/api\/telegram['"`]/,
    'Should define TELEGRAM_BASE constant'
  )
  
  // Check endpoint paths are used
  assert.match(
    source,
    /\/status\//,
    'Should use /status/ endpoint'
  )
  
  assert.match(
    source,
    /\/generate-link\//,
    'Should use /generate-link/ endpoint'
  )
  
  assert.match(
    source,
    /\/unlink\//,
    'Should use /unlink/ endpoint'
  )
  
  assert.match(
    source,
    /\/settings\//,
    'Should use /settings/ endpoint'
  )
})

// ==========================================
// Hooks Tests
// ==========================================

test('useTelegram hook exports all required hooks', () => {
  const source = loadFile(hookPath)
  
  const requiredHooks = [
    'useTelegramStatus',
    'useGenerateTelegramLink',
    'useUnlinkTelegram',
    'useUpdateTelegramSettings'
  ]
  
  requiredHooks.forEach(hook => {
    assert.match(
      source,
      new RegExp(`export\\s+function\\s+${hook}`),
      `Should export ${hook} hook`
    )
  })
})

test('useTelegram hooks use TanStack Query', () => {
  const source = loadFile(hookPath)
  
  assert.match(
    source,
    /from\s+'@tanstack\/react-query'/,
    'Should import from @tanstack/react-query'
  )
  
  assert.match(
    source,
    /useQuery\(/,
    'Should use useQuery'
  )
  
  assert.match(
    source,
    /useMutation\(/,
    'Should use useMutation'
  )
  
  assert.match(
    source,
    /useQueryClient\(/,
    'Should use useQueryClient'
  )
})

test('useTelegram hooks invalidate cache properly', () => {
  const source = loadFile(hookPath)
  
  assert.match(
    source,
    /queryClient\.setQueryData/,
    'Should update cache on success'
  )
})

// ==========================================
// Index Export Tests
// ==========================================

test('Index file exports all components', () => {
  const source = loadFile(indexPath)
  
  assert.match(
    source,
    /TelegramSettings/,
    'Should export TelegramSettings'
  )
  
  assert.match(
    source,
    /TelegramConnect/,
    'Should export TelegramConnect'
  )
  
  assert.match(
    source,
    /TelegramConnected/,
    'Should export TelegramConnected'
  )
  
  assert.match(
    source,
    /export\s+\{?\s*default/,
    'Should have default export'
  )
})
