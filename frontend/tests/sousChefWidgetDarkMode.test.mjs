import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const widgetPath = resolve('src/components/SousChefWidget.jsx')
const selectorPath = resolve('src/components/FamilySelector.jsx')
const chatPath = resolve('src/components/SousChefChat.jsx')

function load(path) {
  return readFileSync(path, 'utf8')
}

function getBlock(source, pattern) {
  const match = source.match(pattern)
  return match ? match[0] : ''
}

test('SousChef panel uses themed surface for dark mode', () => {
  const src = load(widgetPath)
  const block = getBlock(src, /\.sc-panel\s*\{[^}]+\}/)
  assert.ok(block, 'Expected .sc-panel styles.')
  assert.match(block, /background:\s*var\(--sc-surface,\s*var\(--surface/, 'Panel should use themed surface with fallback.')
  assert.match(block, /border:\s*1px solid var\(--sc-border,\s*var\(--border/, 'Panel should use themed border.')
})

test('Family selector trigger and dropdown use themed surfaces', () => {
  const src = load(selectorPath)
  const trigger = getBlock(src, /\.family-selector-trigger\s*\{[^}]+\}/)
  assert.ok(trigger, 'Expected trigger styles.')
  assert.match(trigger, /background:\s*var\(--surface/, 'Trigger background should use themed surface.')

  const dropdown = getBlock(src, /\.family-selector-dropdown\s*\{[^}]+\}/)
  assert.ok(dropdown, 'Expected dropdown styles.')
  assert.match(dropdown, /background:\s*var\(--surface/, 'Dropdown background should use themed surface.')
})

test('SousChef composer input wrapper uses themed surface background', () => {
  const src = load(chatPath)
  const block = getBlock(src, /\.sc-composer-input-wrap\s*\{[^}]+\}/)
  assert.ok(block, 'Expected .sc-composer-input-wrap styles.')
  assert.match(block, /background:\s*var\(--sc-surface-2,\s*var\(--surface-2/, 'Composer input wrapper should use themed surface for dark mode readability.')
})
