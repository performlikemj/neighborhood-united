/**
 * Tests for chefSpecialties module
 * 
 * Run with: node --test src/lib/__tests__/chefSpecialties.test.js
 */

import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  CHEF_SPECIALTIES,
  getSpecialty,
  getSpecialtyLabels,
  formatSpecialties
} from '../chefSpecialties.js'


describe('CHEF_SPECIALTIES', () => {
  it('should have at least 5 specialties defined', () => {
    assert.ok(CHEF_SPECIALTIES.length >= 5)
  })

  it('each specialty should have required fields', () => {
    for (const specialty of CHEF_SPECIALTIES) {
      assert.ok(specialty.id, 'should have an id')
      assert.ok(specialty.label, 'should have a label')
      assert.ok(specialty.emoji, 'should have an emoji')
    }
  })

  it('should have unique IDs', () => {
    const ids = CHEF_SPECIALTIES.map(s => s.id)
    const uniqueIds = new Set(ids)
    assert.equal(ids.length, uniqueIds.size, 'IDs should be unique')
  })
})


describe('getSpecialty', () => {
  it('should return specialty by ID', () => {
    const specialty = getSpecialty('comfort')
    assert.ok(specialty)
    assert.equal(specialty.label, 'Comfort Food')
    assert.equal(specialty.emoji, '🍲')
  })

  it('should return null for unknown ID', () => {
    assert.equal(getSpecialty('unknown'), null)
  })

  it('should return null for empty ID', () => {
    assert.equal(getSpecialty(''), null)
    assert.equal(getSpecialty(null), null)
    assert.equal(getSpecialty(undefined), null)
  })
})


describe('getSpecialtyLabels', () => {
  it('should return labels for valid IDs', () => {
    const labels = getSpecialtyLabels(['comfort', 'health'])
    assert.deepEqual(labels, ['Comfort Food', 'Health-Focused'])
  })

  it('should filter out invalid IDs', () => {
    const labels = getSpecialtyLabels(['comfort', 'invalid', 'health'])
    assert.deepEqual(labels, ['Comfort Food', 'Health-Focused'])
  })

  it('should return empty array for empty input', () => {
    assert.deepEqual(getSpecialtyLabels([]), [])
    assert.deepEqual(getSpecialtyLabels(null), [])
    assert.deepEqual(getSpecialtyLabels(undefined), [])
  })
})


describe('formatSpecialties', () => {
  it('should format specialties with emojis', () => {
    const result = formatSpecialties(['comfort', 'health'])
    assert.equal(result, '🍲 Comfort Food, 🥗 Health-Focused')
  })

  it('should handle single specialty', () => {
    const result = formatSpecialties(['vegan'])
    assert.equal(result, '🌱 Vegan/Plant-Based')
  })

  it('should return empty string for empty input', () => {
    assert.equal(formatSpecialties([]), '')
    assert.equal(formatSpecialties(null), '')
    assert.equal(formatSpecialties(undefined), '')
  })

  it('should skip invalid IDs', () => {
    const result = formatSpecialties(['comfort', 'invalid'])
    assert.equal(result, '🍲 Comfort Food')
  })
})
