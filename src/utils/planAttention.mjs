const noPlanPhrase = 'no plan found'

export function shouldHighlightGenerateButton({ errorMessage, isGenerating, planExistsForWeek } = {}) {
  if (isGenerating) return false
  if (planExistsForWeek) return false

  const normalized = typeof errorMessage === 'string' ? errorMessage.trim().toLowerCase() : ''
  if (!normalized) return false

  return normalized.includes(noPlanPhrase)
}
