/**
 * Analytics tracking utility
 * Provides a unified interface for tracking events across the app.
 * Currently logs to console in development; replace with actual provider.
 */

const isDev = import.meta.env.DEV

export function trackEvent(eventName, properties = {}) {
  const event = {
    name: eventName,
    properties: {
      ...properties,
      timestamp: new Date().toISOString(),
      path: window.location.pathname
    }
  }

  if (isDev) {
    console.log('[Analytics]', event)
  }

  // Uncomment and configure when adding analytics provider:
  // if (window.gtag) {
  //   window.gtag('event', eventName, properties)
  // }
  // if (window.posthog) {
  //   window.posthog.capture(eventName, properties)
  // }
}

// Pre-defined event names for consistency
export const EVENTS = {
  HOME_SEARCH_SUBMITTED: 'home_search_submitted',
  HOME_AUDIENCE_TOGGLED: 'home_audience_toggled',
  HOME_CHEF_CARD_CLICKED: 'home_chef_card_clicked',
  HOME_SERVICE_CARD_CLICKED: 'home_service_card_clicked',
  HOME_CTA_CLICKED: 'home_cta_clicked',
  HOME_CHEF_APPLICATION_STARTED: 'home_chef_application_started',
  HOME_CHEF_APPLICATION_SUBMITTED: 'home_chef_application_submitted'
}

export default { trackEvent, EVENTS }
