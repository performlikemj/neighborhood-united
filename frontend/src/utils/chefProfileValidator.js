/**
 * Chef Profile Validator
 * 
 * Validates that a chef profile meets minimum requirements before going live.
 * Used for Stripe audit compliance and maintaining platform quality standards.
 */

/**
 * Minimum requirements for a chef profile to be considered "complete"
 */
export const PROFILE_REQUIREMENTS = {
  // Basic Info
  bio: {
    required: true,
    minLength: 100,
    label: 'Bio/About section',
    description: 'A detailed bio helps customers understand your background and style'
  },
  experience: {
    required: true,
    minLength: 50,
    label: 'Experience description',
    description: 'Share your culinary experience and expertise'
  },
  
  // Media
  profilePic: {
    required: true,
    label: 'Profile picture',
    description: 'A professional photo helps build trust'
  },
  galleryPhotos: {
    required: true,
    minCount: 3,
    label: 'Gallery photos',
    description: 'Showcase your culinary work with at least 3 photos'
  },
  
  // Services
  serviceOfferings: {
    required: true,
    minCount: 1,
    label: 'Service offering',
    description: 'At least one service with pricing and description'
  },
  
  // Location
  location: {
    required: true,
    label: 'Location/Service area',
    description: 'City/region and postal codes you serve'
  }
}

/**
 * Profile readiness levels
 */
export const PROFILE_STATUS = {
  DRAFT: 'draft',           // Missing critical requirements
  INCOMPLETE: 'incomplete', // Has some requirements, missing others
  READY: 'ready',           // Meets all minimum requirements
  EXCELLENT: 'excellent'    // Exceeds requirements
}

/**
 * Validates a chef profile against requirements
 * @param {Object} profile - Chef profile object
 * @returns {Object} Validation result with status, score, and missing items
 */
export function validateChefProfile(profile) {
  if (!profile) {
    return {
      status: PROFILE_STATUS.DRAFT,
      score: 0,
      isComplete: false,
      missing: Object.keys(PROFILE_REQUIREMENTS),
      details: {}
    }
  }

  const results = {}
  let totalPoints = 0
  const maxPoints = Object.keys(PROFILE_REQUIREMENTS).length
  const missing = []

  // Validate Bio
  const bio = profile.bio || ''
  const bioValid = bio.length >= PROFILE_REQUIREMENTS.bio.minLength
  results.bio = {
    valid: bioValid,
    current: bio.length,
    required: PROFILE_REQUIREMENTS.bio.minLength,
    message: bioValid
      ? `Bio complete (${bio.length} characters)`
      : `Bio too short: ${bio.length}/${PROFILE_REQUIREMENTS.bio.minLength} characters`
  }
  if (bioValid) totalPoints++
  else missing.push('bio')

  // Validate Experience
  const experience = profile.experience || ''
  const expValid = experience.length >= PROFILE_REQUIREMENTS.experience.minLength
  results.experience = {
    valid: expValid,
    current: experience.length,
    required: PROFILE_REQUIREMENTS.experience.minLength,
    message: expValid
      ? `Experience complete (${experience.length} characters)`
      : `Experience too short: ${experience.length}/${PROFILE_REQUIREMENTS.experience.minLength} characters`
  }
  if (expValid) totalPoints++
  else missing.push('experience')

  // Validate Profile Picture
  const hasProfilePic = Boolean(profile.profile_pic_url || profile.profile_pic)
  results.profilePic = {
    valid: hasProfilePic,
    message: hasProfilePic ? 'Profile picture uploaded' : 'No profile picture'
  }
  if (hasProfilePic) totalPoints++
  else missing.push('profilePic')

  // Validate Gallery Photos
  const photos = Array.isArray(profile.photos) ? profile.photos : []
  const photoCount = photos.length
  const photosValid = photoCount >= PROFILE_REQUIREMENTS.galleryPhotos.minCount
  results.galleryPhotos = {
    valid: photosValid,
    current: photoCount,
    required: PROFILE_REQUIREMENTS.galleryPhotos.minCount,
    message: photosValid
      ? `${photoCount} gallery photos`
      : `Only ${photoCount}/${PROFILE_REQUIREMENTS.galleryPhotos.minCount} photos`
  }
  if (photosValid) totalPoints++
  else missing.push('galleryPhotos')

  // Validate Service Offerings
  const offerings = Array.isArray(profile.service_offerings) ? profile.service_offerings : []
  const offeringsValid = offerings.length >= PROFILE_REQUIREMENTS.serviceOfferings.minCount
  results.serviceOfferings = {
    valid: offeringsValid,
    current: offerings.length,
    required: PROFILE_REQUIREMENTS.serviceOfferings.minCount,
    message: offeringsValid
      ? `${offerings.length} service offering(s)`
      : `No service offerings yet`
  }
  if (offeringsValid) totalPoints++
  else missing.push('serviceOfferings')

  // Validate Location
  const hasLocation = Boolean(
    (profile.city || profile.location?.city || profile.address?.city) &&
    (profile.country || profile.location?.country || profile.address?.country ||
     profile.country_code || profile.location?.country_code)
  )
  const hasServiceAreas = Array.isArray(profile.serving_postalcodes) && 
    profile.serving_postalcodes.length > 0
  const locationValid = hasLocation && hasServiceAreas
  results.location = {
    valid: locationValid,
    hasLocation,
    hasServiceAreas,
    message: locationValid
      ? 'Location and service areas configured'
      : !hasLocation
      ? 'City/country not set'
      : 'No service areas defined'
  }
  if (locationValid) totalPoints++
  else missing.push('location')

  // Calculate score and status
  const score = Math.round((totalPoints / maxPoints) * 100)
  const isComplete = missing.length === 0
  
  let status
  if (score === 100) {
    status = PROFILE_STATUS.EXCELLENT
  } else if (score >= 85) {
    status = PROFILE_STATUS.READY
  } else if (score >= 50) {
    status = PROFILE_STATUS.INCOMPLETE
  } else {
    status = PROFILE_STATUS.DRAFT
  }

  return {
    status,
    score,
    isComplete,
    missing,
    details: results,
    totalPoints,
    maxPoints
  }
}

/**
 * Get user-friendly status message
 */
export function getStatusMessage(validation) {
  if (!validation) return ''
  
  const { status, score, missing } = validation
  
  if (status === PROFILE_STATUS.EXCELLENT) {
    return '✅ Your profile is complete and looks great!'
  }
  
  if (status === PROFILE_STATUS.READY) {
    return '✅ Your profile meets all minimum requirements and is ready to go live!'
  }
  
  if (status === PROFILE_STATUS.INCOMPLETE) {
    return `⚠️ Your profile is ${score}% complete. Add ${missing.length} more item(s) to go live.`
  }
  
  return `❌ Your profile needs work (${score}%). Complete ${missing.length} required items before going live.`
}

/**
 * Get actionable recommendations
 */
export function getRecommendations(validation) {
  if (!validation || !validation.missing || validation.missing.length === 0) {
    return []
  }
  
  return validation.missing.map(key => {
    const req = PROFILE_REQUIREMENTS[key]
    const detail = validation.details[key]
    
    return {
      key,
      label: req.label,
      description: req.description,
      current: detail?.current || 0,
      required: detail?.required || req.minCount || 1,
      message: detail?.message || `Missing: ${req.label}`
    }
  })
}

/**
 * Check if profile is ready for Stripe audit
 * (Higher bar than just "complete")
 */
export function isStripeAuditReady(profile) {
  const validation = validateChefProfile(profile)
  
  // Must have all required items
  if (!validation.isComplete) return false
  
  // Additional quality checks for Stripe
  const photoCount = Array.isArray(profile.photos) ? profile.photos.length : 0
  const hasEnoughPhotos = photoCount >= 5 // Prefer 5+ for Stripe
  
  const bioLength = (profile.bio || '').length
  const hasDetailedBio = bioLength >= 150 // Prefer 150+ chars
  
  const hasMultipleServices = Array.isArray(profile.service_offerings) && 
    profile.service_offerings.length >= 2
  
  return hasEnoughPhotos && hasDetailedBio || hasMultipleServices
}

export default {
  validateChefProfile,
  getStatusMessage,
  getRecommendations,
  isStripeAuditReady,
  PROFILE_REQUIREMENTS,
  PROFILE_STATUS
}



