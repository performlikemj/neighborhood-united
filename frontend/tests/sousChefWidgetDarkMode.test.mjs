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

test('SousChef panel seeds themed card variables for dark mode', () => {
  const src = load(widgetPath)
  const block = getBlock(src, /\.sous-chef-panel\s*\{[^}]+\}/)
  assert.ok(block, 'Expected .sous-chef-panel styles.')
  assert.match(block, /--bg-card:\s*var\(--surface/, 'Panel should expose --bg-card tied to themed surface.')
  assert.match(block, /--border-color:\s*var\(--border/, 'Panel should expose --border-color from theme tokens.')
})

test('Family selector trigger and dropdown use themed surfaces', () => {
  const src = load(selectorPath)
  const trigger = getBlock(src, /\.family-selector-trigger\s*\{[^}]+\}/)
  assert.ok(trigger, 'Expected trigger styles.')
  assert.match(trigger, /background:\s*var\(--bg-card/, 'Trigger background should use themed card surface.')

  const dropdown = getBlock(src, /\.family-selector-dropdown\s*\{[^}]+\}/)
  assert.ok(dropdown, 'Expected dropdown styles.')
  assert.match(dropdown, /background:\s*var\(--bg-card/, 'Dropdown background should use themed card surface.')
})

test('SousChef composer input uses themed surface background', () => {
  const src = load(chatPath)
  const block = getBlock(src, /\.composer-input\s*\{[^}]+\}/)
  assert.ok(block, 'Expected composer input styles.')
  assert.match(block, /background:\s*var\(--surface/, 'Composer input should sit on themed surface for dark mode readability.')
})
