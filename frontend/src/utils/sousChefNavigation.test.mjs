import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resolveSousChefNavigation, resolveSousChefPrefillTarget } from './sousChefNavigation.mjs'

test('resolveSousChefNavigation maps Meal Shares to services sub-tab', () => {
  const result = resolveSousChefNavigation({ tab: 'meal-shares' })
  assert.equal(result.tab, 'services')
  assert.equal(result.servicesSubTab, 'meal-shares')
  assert.equal(result.label, 'Meal Shares')
})

test('resolveSousChefNavigation normalizes meal_shares', () => {
  const result = resolveSousChefNavigation({ tab: 'meal_shares' })
  assert.equal(result.tab, 'services')
  assert.equal(result.servicesSubTab, 'meal-shares')
})

test('resolveSousChefPrefillTarget routes event forms to meal shares', () => {
  const result = resolveSousChefPrefillTarget({ form_type: 'event' })
  assert.equal(result.tab, 'services')
  assert.equal(result.servicesSubTab, 'meal-shares')
})

test('resolveSousChefPrefillTarget routes dish forms to menu dishes sub-tab', () => {
  const result = resolveSousChefPrefillTarget({ form_type: 'dish' })
  assert.equal(result.tab, 'menu')
  assert.equal(result.menuSubTab, 'dishes')
})
