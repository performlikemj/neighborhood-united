import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const slideoutPath = resolve('src/components/MealPlanSlideout.jsx')

function loadSlideout() {
  return readFileSync(slideoutPath, 'utf8')
}

function getBlock(source, selectorRegex) {
  const match = source.match(selectorRegex)
  return match ? match[0] : ''
}

test('MealPlan selector applies themed text color for readability', () => {
  const source = loadSlideout()
  const selectBlock = getBlock(source, /\.mps-select\s*\{[^}]+\}/)

  assert.ok(selectBlock, 'MealPlanSlideout should style the .mps-select element.')
  assert.match(
    selectBlock,
    /color:\s*var\(--text[^;]*\)/,
    'Plan selector should use the themed text color so labels remain legible in dark mode.'
  )
})

test('MealPlan selector options inherit themed surface and text colors', () => {
  const source = loadSlideout()
  const optionBlock = getBlock(source, /\.mps-select\s*option\s*\{[^}]+\}/)

  assert.ok(optionBlock, 'Dropdown options should be explicitly styled for theme compatibility.')
  assert.match(
    optionBlock,
    /background:\s*var\(--surface[^;]*\)/,
    'Option background should align with themed surfaces.'
  )
  assert.match(
    optionBlock,
    /color:\s*var\(--text[^;]*\)/,
    'Option text should inherit the themed text color for dark-mode readability.'
  )
})
