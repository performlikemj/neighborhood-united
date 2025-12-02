import test from 'node:test'
import assert from 'node:assert/strict'

import { shouldHighlightGenerateButton } from './planAttention.mjs'

test('highlights generate button when no plan message is shown', () => {
  const result = shouldHighlightGenerateButton({
    errorMessage: 'No plan found. Generate one.',
    isGenerating: false,
    planExistsForWeek: false,
  })

  assert.equal(result, true)
})

test('does not highlight when plan already exists for the week', () => {
  const result = shouldHighlightGenerateButton({
    errorMessage: 'No plan found. Generate one.',
    isGenerating: false,
    planExistsForWeek: true,
  })

  assert.equal(result, false)
})

test('does not highlight while generation is in progress', () => {
  const result = shouldHighlightGenerateButton({
    errorMessage: 'No plan found. Generate one.',
    isGenerating: true,
    planExistsForWeek: false,
  })

  assert.equal(result, false)
})

test('ignores unrelated error messages', () => {
  const result = shouldHighlightGenerateButton({
    errorMessage: 'Network error: timeout',
    isGenerating: false,
    planExistsForWeek: false,
  })

  assert.equal(result, false)
})
