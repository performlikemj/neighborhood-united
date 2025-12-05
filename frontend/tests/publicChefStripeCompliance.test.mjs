/**
 * PublicChef Stripe Connect Compliance Tests
 * 
 * These tests verify that the chef profile page contains all elements
 * required for Stripe Connect approval, including:
 * - Trust badges (Identity Verified, Stripe Verified, Secure Checkout)
 * - Service provider disclosure banner
 * - Legal policy links (Terms, Privacy, Refund)
 * - Payment security messaging
 * - Business legitimacy indicators
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const publicChefPath = resolve('src/pages/PublicChef.jsx')
const stylesPath = resolve('src/styles.css')

function loadPublicChef() {
  return readFileSync(publicChefPath, 'utf8')
}

function loadStyles() {
  return readFileSync(stylesPath, 'utf8')
}

// =============================================================================
// TRUST BADGES - Critical for establishing legitimacy
// =============================================================================

test('PublicChef displays trust badges section for Stripe compliance', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /className="trust-badges"/,
    'Chef profile should have a trust-badges container for displaying verification status.'
  )
})

test('PublicChef shows Identity Verified badge for verified chefs', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Identity Verified/,
    'Chef profile should display "Identity Verified" badge for verified chefs.'
  )
  assert.match(
    source,
    /is_email_verified|is_verified|is_active/,
    'Identity badge should be tied to verification status fields.'
  )
})

test('PublicChef always displays Stripe Verified badge', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Stripe Verified/,
    'Chef profile should always display "Stripe Verified" badge since payments go through Stripe.'
  )
  assert.match(
    source,
    /fa-brands fa-stripe|fa-stripe/,
    'Stripe badge should use the Stripe brand icon.'
  )
})

test('PublicChef always displays Secure Checkout badge', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Secure Checkout/,
    'Chef profile should always display "Secure Checkout" badge.'
  )
  assert.match(
    source,
    /fa-solid fa-credit-card|fa-credit-card/,
    'Secure Checkout badge should use a credit card icon.'
  )
})

test('PublicChef supports Background Checked badge for vetted chefs', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Background Checked/,
    'Chef profile should support displaying "Background Checked" badge.'
  )
  assert.match(
    source,
    /background_checked/,
    'Background Checked badge should be tied to chef.background_checked field.'
  )
})

test('PublicChef supports Insured & Licensed badge', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Insured & Licensed/,
    'Chef profile should support displaying "Insured & Licensed" badge.'
  )
  assert.match(
    source,
    /chef\?\.insured/,
    'Insured badge should be tied to chef.insured field.'
  )
})

// =============================================================================
// SERVICE PROVIDER BANNER - Clear business disclosure
// =============================================================================

test('PublicChef includes service provider banner for business clarity', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /service-provider-banner/,
    'Chef profile should include a service-provider-banner section.'
  )
})

test('PublicChef service provider banner describes the service clearly', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Personal Chef Services/,
    'Banner should clearly state "Personal Chef Services" as the service type.'
  )
  assert.match(
    source,
    /independent personal chef/i,
    'Banner should describe the chef as an independent service provider.'
  )
  assert.match(
    source,
    /professional in-home cooking|meal preparation|catering/i,
    'Banner should describe the actual services offered.'
  )
})

test('PublicChef service provider banner includes business badges', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Independent Business/,
    'Service provider section should show "Independent Business" badge.'
  )
  assert.match(
    source,
    /Service Agreement/,
    'Service provider section should show "Service Agreement" badge.'
  )
  assert.match(
    source,
    /Direct Payments/,
    'Service provider section should show "Direct Payments" badge.'
  )
})

// =============================================================================
// LEGAL POLICY LINKS - Required for Stripe compliance
// =============================================================================

test('PublicChef displays prominent Terms of Service link', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Terms of Service/,
    'Chef profile should display "Terms of Service" link.'
  )
  assert.match(
    source,
    /to="\/terms"|href="\/terms"|\/terms/,
    'Terms of Service should link to /terms page.'
  )
})

test('PublicChef displays prominent Privacy Policy link', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Privacy Policy/,
    'Chef profile should display "Privacy Policy" link.'
  )
  assert.match(
    source,
    /to="\/privacy"|href="\/privacy"|\/privacy/,
    'Privacy Policy should link to /privacy page.'
  )
})

test('PublicChef displays prominent Cancellation & Refund Policy link', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Cancellation & Refund Policy|Refund Policy/,
    'Chef profile should display cancellation/refund policy link.'
  )
  assert.match(
    source,
    /to="\/refund-policy"|href="\/refund-policy"|\/refund-policy/,
    'Refund policy should link to /refund-policy page.'
  )
})

test('PublicChef groups legal policies in a dedicated section', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Legal & Policies|Legal Policies/i,
    'Chef profile should have a dedicated "Legal & Policies" section header.'
  )
})

// =============================================================================
// CONTACT & SUPPORT - Required for customer trust
// =============================================================================

test('PublicChef displays platform support contact', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /support@sautai\.com/,
    'Chef profile should display platform support email.'
  )
  assert.match(
    source,
    /mailto:support@sautai\.com/,
    'Support email should be a clickable mailto link.'
  )
})

test('PublicChef includes Contact & Support section', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Contact & Support/,
    'Chef profile should have a "Contact & Support" section.'
  )
})

test('PublicChef allows reporting issues', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Report an Issue|Report Issue/i,
    'Chef profile should provide a way to report issues.'
  )
})

// =============================================================================
// PAYMENT SECURITY MESSAGING - Stripe approval factor
// =============================================================================

test('PublicChef FAQ mentions Stripe for payment security', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Stripe/i,
    'FAQ or payment section should mention Stripe as the payment processor.'
  )
})

test('PublicChef describes secure payment processing', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /secure|encrypted|protected/i,
    'Chef profile should describe payments as secure.'
  )
})

// =============================================================================
// BOOKING FLOW INTEGRATION
// =============================================================================

test('PublicChef has Book Chef Services CTA', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Book Chef Services?/i,
    'Chef profile should have a "Book Chef Services" call-to-action.'
  )
})

test('PublicChef CTA links to services section', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /#services/,
    'Book Chef Services CTA should link to #services anchor.'
  )
})

test('PublicChef integrates with cart for service booking', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /addItem|addToCart|useCart/i,
    'Chef profile should integrate with cart context for adding services.'
  )
})

// =============================================================================
// CSS STYLES FOR COMPLIANCE ELEMENTS
// =============================================================================

test('Styles include trust-badges styling', () => {
  const styles = loadStyles()
  assert.match(
    styles,
    /\.trust-badges\s*\{/,
    'Styles should define .trust-badges container.'
  )
  assert.match(
    styles,
    /\.trust-badge\s*\{/,
    'Styles should define .trust-badge individual badge styling.'
  )
})

test('Styles include service-provider-banner styling', () => {
  const styles = loadStyles()
  assert.match(
    styles,
    /\.service-provider-banner\s*\{/,
    'Styles should define .service-provider-banner styling.'
  )
})

test('Styles include responsive breakpoints for compliance elements', () => {
  const styles = loadStyles()
  assert.match(
    styles,
    /@media.*max-width.*768px/,
    'Styles should include responsive breakpoints for mobile.'
  )
  assert.match(
    styles,
    /\.trust-badges|\.trust-badge/,
    'Trust badges should have responsive styling.'
  )
})

test('Styles include chef-profile-footer styling', () => {
  const styles = loadStyles()
  assert.match(
    styles,
    /\.chef-profile-footer|\.footer-section|footer/i,
    'Styles should define footer styling for legal/contact sections.'
  )
})

// =============================================================================
// AUTHENTICATION-GATED FEATURES
// =============================================================================

test('PublicChef gates booking actions behind authentication', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /isAuthenticated|user\s*\?\.|!user/,
    'Chef profile should check authentication state for certain actions.'
  )
})

test('PublicChef redirects unauthenticated users for protected actions', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /navigate\s*\(\s*['"`]\/login|\/login/,
    'Protected actions should redirect to login for unauthenticated users.'
  )
})

// =============================================================================
// SERVICE DESCRIPTION CLARITY
// =============================================================================

test('PublicChef displays chef bio/description', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /chef\.bio|chef\.description|chef\?\.bio/,
    'Chef profile should display the chef bio/description.'
  )
})

test('PublicChef displays chef location', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /chef\.city|chef\.country|location/i,
    'Chef profile should display chef location information.'
  )
})

test('PublicChef displays service area information', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /Serves|service_area|serves_area/i,
    'Chef profile should indicate service area coverage.'
  )
})

