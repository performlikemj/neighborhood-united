import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dashboardPath = resolve('src/pages/ChefDashboard.jsx')
const widgetPath = resolve('src/components/SousChefWidget.jsx')

function load(path) {
  return readFileSync(path, 'utf8')
}

test('ChefDashboard includes SousChefWidget for chef assistance', () => {
  const src = load(dashboardPath)
  assert.match(src, /import SousChefWidget/, 'ChefDashboard should import SousChefWidget component.')
  assert.match(src, /<SousChefWidget/, 'ChefDashboard should render SousChefWidget.')
})

test('SousChefWidget receives chef emoji configuration', () => {
  const src = load(dashboardPath)
  assert.match(src, /sousChefEmoji=/, 'SousChefWidget should receive sousChefEmoji prop.')
  assert.match(src, /onEmojiChange=/, 'SousChefWidget should receive onEmojiChange callback.')
})

test('SousChefWidget is wrapped in notification provider', () => {
  const src = load(dashboardPath)
  assert.match(src, /SousChefNotificationProvider/, 'ChefDashboard should use SousChefNotificationProvider.')
})
