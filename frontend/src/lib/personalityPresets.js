/**
 * Personality Presets for Sous Chef
 * 
 * Defines the preset personalities chefs can choose from,
 * and utility functions for detecting which preset matches a given soul_prompt.
 */

/**
 * Personality presets with their soul_prompt templates
 */
export const PERSONALITY_PRESETS = {
  professional: {
    id: 'professional',
    label: 'Professional',
    emoji: '👔',
    description: 'Clear, formal, to the point',
    prompt: `Communicate in a professional, clear manner.
Be respectful and formal in all interactions.
Focus on facts and actionable information.
Keep responses concise and well-organized.
Use proper culinary terminology when appropriate.
Maintain a business-appropriate tone at all times.`
  },
  friendly: {
    id: 'friendly',
    label: 'Friendly',
    emoji: '😊',
    description: 'Warm, supportive, encouraging',
    prompt: `Be warm, friendly, and encouraging in all interactions.
Use casual, conversational language.
Celebrate wins and offer genuine support when things are tough.
Remember personal details and bring them up naturally.
Use occasional emojis to add warmth.
Make the chef feel like you're a trusted kitchen partner.`
  },
  efficient: {
    id: 'efficient',
    label: 'Efficient',
    emoji: '⚡',
    description: 'Short, direct, no fluff',
    prompt: `Be extremely concise and direct.
Use bullet points over paragraphs when possible.
Skip pleasantries and filler words.
Provide only essential information.
Get straight to the point in every response.
Prioritize speed and clarity over elaboration.`
  }
}

/**
 * Get all preset IDs
 * @returns {string[]} Array of preset IDs
 */
export function getPresetIds() {
  return Object.keys(PERSONALITY_PRESETS)
}

/**
 * Get a preset by ID
 * @param {string} id - The preset ID
 * @returns {object|null} The preset object or null if not found
 */
export function getPreset(id) {
  return PERSONALITY_PRESETS[id] || null
}

/**
 * Detect which preset (if any) matches the current soul_prompt
 * Uses normalized comparison to account for whitespace differences
 * 
 * @param {string} soulPrompt - The current soul_prompt to check
 * @returns {string|null} The preset ID that matches, 'custom' if modified, or null if empty
 */
export function detectPreset(soulPrompt) {
  if (!soulPrompt || soulPrompt.trim() === '') {
    return null
  }

  const normalized = soulPrompt.trim().toLowerCase()
  
  for (const [id, preset] of Object.entries(PERSONALITY_PRESETS)) {
    const presetNormalized = preset.prompt.trim().toLowerCase()
    
    // Exact match
    if (normalized === presetNormalized) {
      return id
    }
    
    // Check if it starts the same way (user may have added to preset)
    if (normalized.startsWith(presetNormalized.slice(0, 50))) {
      // If they've modified it significantly (>20% longer), treat as custom
      if (normalized.length > presetNormalized.length * 1.2) {
        return 'custom'
      }
      return id
    }
  }
  
  return 'custom'
}

/**
 * Check if a soul_prompt is a known preset (not custom)
 * @param {string} soulPrompt - The soul_prompt to check
 * @returns {boolean} True if it matches a known preset
 */
export function isKnownPreset(soulPrompt) {
  const detected = detectPreset(soulPrompt)
  return detected !== null && detected !== 'custom'
}

/**
 * Get the default preset to use for new chefs
 * @returns {object} The default preset object
 */
export function getDefaultPreset() {
  return PERSONALITY_PRESETS.friendly
}
