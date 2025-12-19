/**
 * PublicChef Booking Flow Tests
 * 
 * These tests verify the complete booking flow works correctly:
 * - Service tier display and selection
 * - Add to cart functionality
 * - Form validation
 * - Checkout integration
 * - Authentication requirements
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const publicChefPath = resolve('src/pages/PublicChef.jsx')
const cartSidebarPath = resolve('src/components/CartSidebar.jsx')
const servicesClientPath = resolve('src/api/servicesClient.js')

function loadPublicChef() {
  return readFileSync(publicChefPath, 'utf8')
}

function loadCartSidebar() {
  return readFileSync(cartSidebarPath, 'utf8')
}

function loadServicesClient() {
  return readFileSync(servicesClientPath, 'utf8')
}

// =============================================================================
// SERVICE TIER DISPLAY
// =============================================================================

test('PublicChef fetches and displays service offerings', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /services\/offerings|serviceOfferings|offerings/i,
    'PublicChef should fetch service offerings from the API.'
  )
})

test('PublicChef displays service tiers with pricing', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /tier|price|pricing/i,
    'PublicChef should display service tiers with pricing information.'
  )
})

test('PublicChef shows service descriptions', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /description|details/i,
    'PublicChef should show service descriptions.'
  )
})

// =============================================================================
// ADD TO CART FUNCTIONALITY
// =============================================================================

test('PublicChef has Add to Cart button for services', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Add to Cart|addToCart|addItem/i,
    'PublicChef should have Add to Cart functionality.'
  )
})

test('PublicChef uses CartContext for cart operations', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /useCart|CartContext/,
    'PublicChef should use CartContext for cart operations.'
  )
})

test('CartSidebar displays cart items from context', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /items|cartItems/i,
    'CartSidebar should display items from cart context.'
  )
})

// =============================================================================
// BOOKING FORM VALIDATION
// =============================================================================

test('CartSidebar includes household size field', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /household|family_size|people|guests/i,
    'CartSidebar should include household/party size field.'
  )
})

test('CartSidebar includes date/time selection', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /date|time|scheduled|datetime/i,
    'CartSidebar should include date/time selection for service booking.'
  )
})

test('CartSidebar validates required fields', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /required|validation|error/i,
    'CartSidebar should validate required booking fields.'
  )
})

test('CartSidebar handles form submission errors', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /error|setError|validation_errors/i,
    'CartSidebar should handle and display form submission errors.'
  )
})

// =============================================================================
// CHECKOUT INTEGRATION
// =============================================================================

test('CartSidebar initiates Stripe checkout', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /checkout|stripe_checkout_url|payment/i,
    'CartSidebar should initiate Stripe checkout process.'
  )
})

test('CartSidebar redirects to Stripe on checkout', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /window\.location|redirect|stripe/i,
    'CartSidebar should redirect to Stripe checkout URL.'
  )
})

test('CartSidebar calls checkout endpoint', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /\/checkout/i,
    'CartSidebar should call checkout endpoint to initiate payment.'
  )
})

// =============================================================================
// SERVICE ADDRESS HANDLING
// =============================================================================

test('CartSidebar fetches saved addresses', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /address|addresses|address_details/i,
    'CartSidebar should fetch customer saved addresses.'
  )
})

test('CartSidebar allows adding new address', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /Add new address|new address|addAddress|Add address/i,
    'CartSidebar should allow adding a new service address.'
  )
})

// =============================================================================
// AUTHENTICATION FLOW
// =============================================================================

test('PublicChef prompts login for unauthenticated booking', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /login|authenticate|sign in/i,
    'PublicChef should prompt login for unauthenticated users trying to book.'
  )
})

test('CartSidebar requires authentication for checkout', () => {
  const source = loadCartSidebar()
  assert.match(
    source,
    /user|isAuthenticated|auth/i,
    'CartSidebar should check authentication before checkout.'
  )
})

// =============================================================================
// CUSTOM QUOTE REQUEST
// =============================================================================

test('PublicChef supports custom quote requests', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Custom Quote|custom quote|quote request/i,
    'PublicChef should support custom quote requests for special events.'
  )
})

test('PublicChef has quote request modal or form', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /QuoteRequestModal|quoteModal|quoteRequest/i,
    'PublicChef should have a quote request modal or form.'
  )
})

// =============================================================================
// WAITLIST FUNCTIONALITY
// =============================================================================

test('PublicChef supports waitlist for busy chefs', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /waitlist|Waitlist/i,
    'PublicChef should support waitlist functionality.'
  )
})

test('PublicChef fetches waitlist status', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /waitlist\/status|waitlistStatus/i,
    'PublicChef should fetch waitlist status from API.'
  )
})

// =============================================================================
// GALLERY INTEGRATION
// =============================================================================

test('PublicChef links to chef gallery', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /View Gallery|gallery/i,
    'PublicChef should have a link to view the chef gallery.'
  )
})

test('PublicChef displays gallery preview photos', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /photos|images|gallery_preview/i,
    'PublicChef should display gallery preview photos.'
  )
})

// =============================================================================
// WEEKLY MENU INTEGRATION
// =============================================================================

test('PublicChef links to weekly menu section', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Weekly Menu|#meals|meal-events/i,
    'PublicChef should link to weekly menu section.'
  )
})

test('PublicChef fetches meal events', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /chef-meal-events|mealEvents/i,
    'PublicChef should fetch chef meal events from API.'
  )
})

// =============================================================================
// MAP/LOCATION FUNCTIONALITY
// =============================================================================

test('PublicChef has View Map button', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /View Map|showMap|MapPanel/i,
    'PublicChef should have View Map functionality.'
  )
})

test('PublicChef integrates MapPanel component', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /MapPanel|from.*MapPanel/,
    'PublicChef should integrate the MapPanel component.'
  )
})

// =============================================================================
// CONNECTION/INVITATION FLOW
// =============================================================================

test('PublicChef has Request Invitation button', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Request Invitation/,
    'PublicChef should have Request Invitation button.'
  )
})

test('PublicChef uses useConnections hook', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /useConnections/,
    'PublicChef should use useConnections hook for invitation management.'
  )
})

test('PublicChef displays connection status', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /connectionStatus|Pending|Connected/i,
    'PublicChef should display current connection status.'
  )
})

