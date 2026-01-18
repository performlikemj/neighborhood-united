/**
 * Configuration constants for the home page
 * Centralized to avoid magic numbers and enable easy adjustments
 */
export const HOME_CONFIG = {
  // API pagination
  CHEF_PAGE_SIZE: 100,
  FEATURED_CHEFS_LIMIT: 8,

  // Animation durations (ms)
  CHEF_COUNTER_DURATION: 2000,
  CITY_COUNTER_DURATION: 1800,

  // Text truncation
  BIO_MAX_LENGTH: 80
}

export default HOME_CONFIG
