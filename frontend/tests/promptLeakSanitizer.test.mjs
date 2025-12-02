import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { stripPromptLeak, scrubPromptLeaks } from '../src/utils/promptSanitizer.mjs'

test('stripPromptLeak removes internal prompt scaffolding', () => {
  const sample = [
    'Batch user prompt: Create a complete meal plan for 2025-10-20.',
    'Include detailed macros.',
    'Return JSON following the PromptMealMap schema with day and meal_type slots.',
    'Request id: batch-2025-10-20.',
    'Final plated meal: Citrus Salmon with Quinoa.'
  ].join('\n')
  const cleaned = stripPromptLeak(sample)
  assert.equal(cleaned, 'Final plated meal: Citrus Salmon with Quinoa.')
})

test('stripPromptLeak preserves normal descriptions', () => {
  const plain = 'Savory mushroom risotto with parmesan and herbs.'
  assert.equal(stripPromptLeak(plain), plain)
})

test('scrubPromptLeaks recursively sanitizes nested payloads', () => {
  const payload = {
    summary: 'Batch user prompt: cook dinner\nReturn JSON after this line.',
    meals: [
      {
        name: 'Roasted chicken',
        description: 'Request id: abc123\nJuicy roasted chicken with vegetables.'
      }
    ]
  }
  const cleaned = scrubPromptLeaks(payload)
  assert.equal(cleaned.summary, '')
  assert.equal(cleaned.meals[0].description, 'Juicy roasted chicken with vegetables.')
})

test('MealPlans sanitizes meal descriptions before render', () => {
  const source = readFileSync('src/pages/MealPlans.jsx', 'utf8')
  assert.match(
    source,
    /import\s+{[^}]*stripPromptLeak[^}]*}\s+from\s+'..\/utils\/promptSanitizer\.(?:mjs|js)'/,
    'Expected MealPlans to import stripPromptLeak from the prompt sanitizer utility.'
  )
  assert.match(
    source,
    /const\s+desc\s*=\s*stripPromptLeak\(/,
    'Expected MealPlans to sanitize the description with stripPromptLeak before rendering.'
  )
})

test('API layer applies scrubPromptLeaks to responses', () => {
  const source = readFileSync('src/api.js', 'utf8')
  assert.match(
    source,
    /scrubPromptLeaks\(/,
    'Expected API module to apply scrubPromptLeaks within the response interceptor.'
  )
})
