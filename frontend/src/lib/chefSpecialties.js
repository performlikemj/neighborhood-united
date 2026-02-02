/**
 * Chef Specialties for profile settings.
 * 
 * These are used in the WorkspaceSettings Profile tab
 * to let chefs identify their cooking style/focus.
 */

export const CHEF_SPECIALTIES = [
  { id: 'comfort', label: 'Comfort Food', emoji: '🍲' },
  { id: 'fine-dining', label: 'Fine Dining', emoji: '🍽️' },
  { id: 'meal-prep', label: 'Meal Prep', emoji: '📦' },
  { id: 'health', label: 'Health-Focused', emoji: '🥗' },
  { id: 'international', label: 'International', emoji: '🌍' },
  { id: 'baking', label: 'Baking & Pastry', emoji: '🧁' },
  { id: 'vegan', label: 'Vegan/Plant-Based', emoji: '🌱' },
  { id: 'bbq', label: 'BBQ & Grilling', emoji: '🔥' },
  { id: 'seafood', label: 'Seafood', emoji: '🦐' },
  { id: 'family', label: 'Family Meals', emoji: '👨‍👩‍👧‍👦' },
]

/**
 * Get a specialty by ID
 * @param {string} id - The specialty ID
 * @returns {object|null} The specialty object or null if not found
 */
export function getSpecialty(id) {
  return CHEF_SPECIALTIES.find(s => s.id === id) || null
}

/**
 * Get specialty labels for a list of IDs
 * @param {string[]} ids - Array of specialty IDs
 * @returns {string[]} Array of labels
 */
export function getSpecialtyLabels(ids) {
  if (!Array.isArray(ids)) return []
  return ids
    .map(id => getSpecialty(id))
    .filter(Boolean)
    .map(s => s.label)
}

/**
 * Get specialty display string (e.g., "🍲 Comfort Food, 🥗 Health-Focused")
 * @param {string[]} ids - Array of specialty IDs
 * @returns {string} Formatted display string
 */
export function formatSpecialties(ids) {
  if (!Array.isArray(ids) || ids.length === 0) return ''
  return ids
    .map(id => {
      const s = getSpecialty(id)
      return s ? `${s.emoji} ${s.label}` : null
    })
    .filter(Boolean)
    .join(', ')
}

export default CHEF_SPECIALTIES
