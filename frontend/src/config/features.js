/**
 * Feature flags for gradual feature rollout.
 * 
 * These flags allow us to enable/disable features during the transition
 * from standalone meal planning to chef-first client portal.
 */

export const FEATURES = {
  // ==========================================================================
  // Customer Features (Deprecated / Being Phased Out)
  // ==========================================================================
  
  /**
   * Allow customers to generate their own meal plans without a chef.
   * Deprecated: Customers should use chef-created plans instead.
   * Keeping enabled temporarily for existing users.
   */
  CUSTOMER_STANDALONE_MEAL_PLANS: false,
  
  /**
   * Generic AI chat for customers (MJ assistant).
   * Deprecated: Customers will interact through chef-curated experience.
   */
  CUSTOMER_AI_CHAT: false,
  
  /**
   * Health metrics tracking (weight, BMI, mood, energy).
   * Deprecated: Not part of chef-first model.
   */
  CUSTOMER_HEALTH_TRACKING: false,
  
  /**
   * Emergency pantry supplies feature.
   * Deprecated: Not part of chef-first model.
   */
  CUSTOMER_EMERGENCY_SUPPLIES: false,
  
  /**
   * Standalone grocery lists for customers.
   * Deprecated: Grocery lists should come from chef meal plans.
   */
  CUSTOMER_GROCERY_LISTS: false,
  
  // ==========================================================================
  // Client Portal Features (New)
  // ==========================================================================
  
  /**
   * My Chefs hub for connected customers.
   * Central place to view chef connections and meal plans.
   */
  CLIENT_PORTAL_MY_CHEFS: true,
  
  /**
   * Collaborative meal planning where customers can suggest changes.
   */
  CLIENT_PORTAL_MEAL_SUGGESTIONS: true,
  
  /**
   * Multi-chef support - customers can connect with multiple chefs.
   */
  CLIENT_PORTAL_MULTI_CHEF: true,
  
  // ==========================================================================
  // Chef Features (All Enabled)
  // ==========================================================================
  
  /**
   * AI Sous Chef assistant for chefs.
   */
  CHEF_AI_SOUS_CHEF: true,
  
  /**
   * Chef meal plan creator for clients.
   */
  CHEF_MEAL_PLAN_CREATOR: true,
  
  /**
   * Chef CRM client management.
   */
  CHEF_CLIENT_MANAGEMENT: true,
  
  /**
   * Chef CRM lead pipeline.
   */
  CHEF_LEAD_PIPELINE: true,
  
  // ==========================================================================
  // Preview Mode Features
  // ==========================================================================
  
  /**
   * Sample meal plan preview for users without chef access.
   */
  PREVIEW_SAMPLE_PLAN: true,
  
  /**
   * Area waitlist for users to be notified when chefs become available.
   */
  PREVIEW_AREA_WAITLIST: true,
}

/**
 * Check if a feature is enabled.
 * @param {string} featureName - The feature flag name
 * @returns {boolean}
 */
export function isFeatureEnabled(featureName) {
  return FEATURES[featureName] === true
}

/**
 * Check if customer standalone features are available.
 * Used to determine if legacy routes should be shown.
 * @returns {boolean}
 */
export function hasLegacyCustomerFeatures() {
  return (
    FEATURES.CUSTOMER_STANDALONE_MEAL_PLANS ||
    FEATURES.CUSTOMER_AI_CHAT ||
    FEATURES.CUSTOMER_HEALTH_TRACKING
  )
}

/**
 * Check if client portal features are available.
 * @returns {boolean}
 */
export function hasClientPortalFeatures() {
  return FEATURES.CLIENT_PORTAL_MY_CHEFS
}

export default FEATURES




