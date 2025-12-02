import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const chefDashboardPath = resolve('src/pages/ChefDashboard.jsx')

function loadSource(){
  return readFileSync(chefDashboardPath, 'utf8')
}

test('ChefDashboard adds a dedicated mealSaving state guard', () => {
  const source = loadSource()
  assert.match(
    source,
    /const\s+\[\s*mealSaving\s*,\s*setMealSaving\s*\]\s*=\s*useState\(\s*false\s*\)/,
    'Expected ChefDashboard to declare mealSaving state set to false by default.'
  )
  assert.match(
    source,
    /const\s+createMeal\s*=\s*async\s*\([^)]*\)\s*=>\s*\{[\s\S]*?if\s*\(\s*mealSaving\s*\)\s*return/,
    'createMeal should bail out early when a submission is already in progress.'
  )
  assert.match(
    source,
    /setMealSaving\(\s*true\s*\)[\s\S]*?api\.post\(\s*['"]\/meals\/api\/chef\/meals\/["']\s*,/,
    'createMeal should set mealSaving to true before posting the new meal.'
  )
  assert.match(
    source,
    /finally\s*\{[\s\S]*?setMealSaving\(\s*false\s*\)/,
    'createMeal must reset mealSaving back to false in a finally block.'
  )
})

test('Meal creation buttons reflect the mealSaving state', () => {
  const source = loadSource()
  assert.match(
    source,
    /<button[\s\S]*?disabled=\{[\s\S]*?mealSaving[\s\S]*?\}[\s\S]*?>\{\s*mealSaving\s*\?[\s\S]*'Saving…'[\s\S]*: [\s\S]*'Create'\s*\}\s*<\/button>/,
    'Quick-create meal button should disable and show Saving… while mealSaving is true.'
  )
  assert.match(
    source,
    /<button[\s\S]*?disabled=\{[\s\S]*?mealSaving[\s\S]*?\}[\s\S]*?>\{\s*mealSaving\s*\?[\s\S]*'Saving…'[\s\S]*: [\s\S]*'Create Meal'\s*\}\s*<\/button>/,
    'Meals tab create button should disable and show Saving… while mealSaving is true.'
  )
})

test('Meal creation dispatches an informational toast before submission', () => {
  const source = loadSource()
  assert.match(
    source,
    /window\.dispatchEvent\(new\s+CustomEvent\('global-toast',[\s\S]*?text:\s*'Creating meal…',[\s\S]*?tone:\s*'info'/,
    'Expected createMeal to announce the start of meal creation via an info toast.'
  )
})

test('ChefDashboard uses checkbox dish selectors instead of multi-selects', () => {
  const source = loadSource()
  assert.ok(
    !/select[^>]+multiple[^>]+dishes/.test(source),
    'Meal dish selection should not rely on a multi-select element.'
  )
  assert.match(
    source,
    /const\s+toggleMealDish\s*=\s*\(/,
    'Expected a toggleMealDish helper to manage checkbox interactions.'
  )
  assert.match(
    source,
    /type="checkbox"[\s\S]*toggleMealDish/,
    'Dish selection inputs should be checkboxes that call toggleMealDish.'
  )
})

test('Dish checklist offers a search filter and scroll container', () => {
  const source = loadSource()
  assert.match(
    source,
    /const\s+\[\s*dishFilter\s*,\s*setDishFilter\s*\]\s*=\s*useState\(\s*''\s*\)/,
    'Expected ChefDashboard to track a dishFilter state.'
  )
  assert.match(
    source,
    /type="search"[\s\S]{0,180}?value=\{dishFilter\}/,
    'renderDishChecklist should render a search input bound to dishFilter.'
  )
  assert.match(
    source,
    /style=\{\{[^}]*maxHeight:\s*['"]?\d+[^}]*overflowY:\s*'auto'/,
    'The dish checklist wrapper should constrain height and scroll overflow.'
  )
})

test('createMeal performs client-side validation before posting', () => {
  const source = loadSource()
  assert.match(
    source,
    /const\s+fieldErrors\s*=\s*\[\]/,
    'createMeal should accumulate fieldErrors before submission.'
  )
  assert.match(
    source,
    /if\s*\(\s*fieldErrors\.length\s*>\s*0\s*\)\s*\{[\s\S]*?setMealSaving\(\s*false\s*\)[\s\S]*?return/,
    'createMeal should bail early when client-side validation fails.'
  )
  assert.match(
    source,
    /fieldErrors\[0\][\s\S]*tone:'error'/,
    'Validation failures should surface via an error toast.'
  )
})
