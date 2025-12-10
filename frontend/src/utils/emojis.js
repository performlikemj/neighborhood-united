/**
 * Diverse emoji utilities for inclusive representation
 */

// Chef emojis with diverse skin tones and genders
export const CHEF_EMOJIS = [
  '👨‍🍳', '👩‍🍳', '🧑‍🍳',           // Default skin tone
  '👨🏻‍🍳', '👩🏻‍🍳', '🧑🏻‍🍳',     // Light
  '👨🏼‍🍳', '👩🏼‍🍳', '🧑🏼‍🍳',     // Medium-Light  
  '👨🏽‍🍳', '👩🏽‍🍳', '🧑🏽‍🍳',     // Medium
  '👨🏾‍🍳', '👩🏾‍🍳', '🧑🏾‍🍳',     // Medium-Dark
  '👨🏿‍🍳', '👩🏿‍🍳', '🧑🏿‍🍳',     // Dark
]

/**
 * Get a random chef emoji for inclusive representation
 * @returns {string} A randomly selected chef emoji
 */
export function getRandomChefEmoji() {
  return CHEF_EMOJIS[Math.floor(Math.random() * CHEF_EMOJIS.length)]
}

/**
 * Get a seeded random chef emoji (stable for a given seed)
 * Useful for consistent display per user/item
 * @param {string|number} seed - A seed value (e.g., user ID, chef ID)
 * @returns {string} A deterministically selected chef emoji
 */
export function getSeededChefEmoji(seed) {
  const hash = String(seed).split('').reduce((acc, char) => {
    return ((acc << 5) - acc) + char.charCodeAt(0)
  }, 0)
  return CHEF_EMOJIS[Math.abs(hash) % CHEF_EMOJIS.length]
}


