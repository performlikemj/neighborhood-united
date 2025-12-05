import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const pickerPath = resolve('src/components/MealSlotPicker.jsx')

function loadPicker() {
  return readFileSync(pickerPath, 'utf8')
}

function getBlock(source, pattern) {
  const match = source.match(pattern)
  return match ? match[0] : ''
}

test('Meal slot search input uses themed surface and text colors', () => {
  const source = loadPicker()
  const block = getBlock(source, /\.msp-search\s*input\s*\{[^}]+\}/)
  assert.ok(block, 'Expected styles for .msp-search input.')
  assert.match(block, /background:\s*var\(--surface[^;]*\)/, 'Search field should sit on themed surface (dark friendly).')
  assert.match(block, /color:\s*var\(--text[^;]*\)/, 'Search field should use themed text color for legibility.')
})

test('Meal slot search placeholder is muted for dark mode', () => {
  const source = loadPicker()
  const block = getBlock(source, /\.msp-search\s*input::placeholder\s*\{[^}]+\}/)
  assert.ok(block, 'Expected placeholder styling for .msp-search input.')
  assert.match(block, /color:\s*var\(--muted[^;]*\)/, 'Placeholder should use muted themed color so it is readable but subtle.')
})

test('Modal surface uses themed background (not plain white)', () => {
  const source = loadPicker()
  const block = getBlock(source, /\.msp-modal\s*\{[^}]+\}/)
  assert.ok(block, 'Expected modal container styles.')
  assert.match(
    block,
    /background:\s*var\(--surface[^;]*\)/,
    'Modal should sit on themed surface for dark mode.'
  )
})

test('Compose chips adopt themed surfaces and text', () => {
  const source = loadPicker()
  const block = getBlock(source, /\.msp-compose-chip\s*\{[^}]+\}/)
  assert.ok(block, 'Expected chip styling for compose selections.')
  assert.match(block, /background:\s*var\(--surface[^;]*\)/, 'Chips should use themed surface background.')
  assert.match(block, /color:\s*var\(--primary[^;]*\)/, 'Chips should keep on-brand primary text in both themes.')
})

test('AI error alert uses themed surfaces and borders', () => {
  const source = loadPicker()
  const block = getBlock(source, /\.msp-ai-error\s*\{[^}]+\}/)
  assert.ok(block, 'Expected AI error styling block.')
  assert.match(block, /background:\s*(color-mix|var\(--surface[^;]*\))/,
    'Alert background should be theme-aware instead of fixed light red.')
  assert.match(block, /border:\s*1px\s+solid\s+(color-mix|var\(--border[^;]*\))/,
    'Alert border should rely on theme tokens.')
  assert.match(block, /color:\s*var\(--text[^;]*\)|#dc2626/,
    'Alert text should remain legible in dark mode.')
})
