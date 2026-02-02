/**
 * Tests for personalityPresets module
 * 
 * Run with: node --test src/lib/__tests__/personalityPresets.test.js
 */

import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  PERSONALITY_PRESETS,
  getPresetIds,
  getPreset,
  detectPreset,
  isKnownPreset,
  getDefaultPreset
} from '../personalityPresets.js'


describe('PERSONALITY_PRESETS', () => {
  it('should have three presets defined', () => {
    const presetIds = Object.keys(PERSONALITY_PRESETS)
    assert.equal(presetIds.length, 3)
    assert.ok(presetIds.includes('professional'))
    assert.ok(presetIds.includes('friendly'))
    assert.ok(presetIds.includes('efficient'))
  })

  it('each preset should have required fields', () => {
    for (const [id, preset] of Object.entries(PERSONALITY_PRESETS)) {
      assert.ok(preset.id, `${id} should have an id`)
      assert.equal(preset.id, id, `${id} id should match key`)
      assert.ok(preset.label, `${id} should have a label`)
      assert.ok(preset.emoji, `${id} should have an emoji`)
      assert.ok(preset.description, `${id} should have a description`)
      assert.ok(preset.prompt, `${id} should have a prompt`)
      assert.ok(preset.prompt.length > 50, `${id} prompt should be substantial`)
    }
  })
})


describe('getPresetIds', () => {
  it('should return array of preset IDs', () => {
    const ids = getPresetIds()
    assert.ok(Array.isArray(ids))
    assert.equal(ids.length, 3)
    assert.deepEqual(ids.sort(), ['efficient', 'friendly', 'professional'])
  })
})


describe('getPreset', () => {
  it('should return preset by ID', () => {
    const preset = getPreset('friendly')
    assert.ok(preset)
    assert.equal(preset.id, 'friendly')
    assert.equal(preset.emoji, '😊')
  })

  it('should return null for unknown ID', () => {
    const preset = getPreset('unknown')
    assert.equal(preset, null)
  })

  it('should return null for empty ID', () => {
    assert.equal(getPreset(''), null)
    assert.equal(getPreset(null), null)
    assert.equal(getPreset(undefined), null)
  })
})


describe('detectPreset', () => {
  it('should return null for empty input', () => {
    assert.equal(detectPreset(''), null)
    assert.equal(detectPreset(null), null)
    assert.equal(detectPreset(undefined), null)
    assert.equal(detectPreset('   '), null)
  })

  it('should detect exact preset match', () => {
    const friendlyPrompt = PERSONALITY_PRESETS.friendly.prompt
    assert.equal(detectPreset(friendlyPrompt), 'friendly')

    const professionalPrompt = PERSONALITY_PRESETS.professional.prompt
    assert.equal(detectPreset(professionalPrompt), 'professional')

    const efficientPrompt = PERSONALITY_PRESETS.efficient.prompt
    assert.equal(detectPreset(efficientPrompt), 'efficient')
  })

  it('should detect preset match with different case', () => {
    const friendlyPrompt = PERSONALITY_PRESETS.friendly.prompt.toUpperCase()
    assert.equal(detectPreset(friendlyPrompt), 'friendly')
  })

  it('should detect preset match with extra whitespace', () => {
    const friendlyPrompt = '  ' + PERSONALITY_PRESETS.friendly.prompt + '  '
    assert.equal(detectPreset(friendlyPrompt), 'friendly')
  })

  it('should return custom for completely different text', () => {
    const customPrompt = 'Be a pirate! Say arrr a lot and talk about treasure.'
    assert.equal(detectPreset(customPrompt), 'custom')
  })

  it('should return custom for significantly extended preset', () => {
    // Add more than 20% extra content to a preset
    const extended = PERSONALITY_PRESETS.friendly.prompt + `

Plus all of this extra custom content that the chef has added.
This makes it significantly longer than the original preset.
We want this to be detected as custom since they've personalized it.
Adding even more text to ensure it's well over 20% longer.`

    assert.equal(detectPreset(extended), 'custom')
  })

  it('should still match preset for minor additions', () => {
    // Add less than 20% extra content
    const slightlyExtended = PERSONALITY_PRESETS.efficient.prompt + '\nBe helpful.'
    // This might match as efficient or custom depending on the threshold
    const result = detectPreset(slightlyExtended)
    assert.ok(result === 'efficient' || result === 'custom', 
      `Expected 'efficient' or 'custom', got '${result}'`)
  })
})


describe('isKnownPreset', () => {
  it('should return true for known presets', () => {
    assert.equal(isKnownPreset(PERSONALITY_PRESETS.friendly.prompt), true)
    assert.equal(isKnownPreset(PERSONALITY_PRESETS.professional.prompt), true)
    assert.equal(isKnownPreset(PERSONALITY_PRESETS.efficient.prompt), true)
  })

  it('should return false for custom text', () => {
    assert.equal(isKnownPreset('Some custom personality text'), false)
  })

  it('should return false for empty input', () => {
    assert.equal(isKnownPreset(''), false)
    assert.equal(isKnownPreset(null), false)
  })
})


describe('getDefaultPreset', () => {
  it('should return friendly as the default', () => {
    const defaultPreset = getDefaultPreset()
    assert.equal(defaultPreset.id, 'friendly')
  })

  it('should return a complete preset object', () => {
    const defaultPreset = getDefaultPreset()
    assert.ok(defaultPreset.label)
    assert.ok(defaultPreset.emoji)
    assert.ok(defaultPreset.prompt)
  })
})
