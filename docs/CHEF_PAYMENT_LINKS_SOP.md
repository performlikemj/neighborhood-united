# Chef Payment Links - Standard Operating Procedure

## Overview

The **Payment Links** feature in Chef Hub enables chefs to create and send professional payment requests to clients for services rendered. Integrated with Stripe, it provides a secure, trackable way to collect payments without the complexity of traditional invoicing.

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Key Features](#key-features)
3. [Prerequisites](#prerequisites)
4. [How It Works](#how-it-works)
5. [Step-by-Step Guide](#step-by-step-guide)
6. [Understanding the Interface](#understanding-the-interface)
7. [Email Verification](#email-verification)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Independent chefs often struggle with payment collection:
- Creating invoices is time-consuming
- Chasing payments is awkward
- Cash/Venmo payments are hard to track
- No professional record of transactions
- Difficult to track who has paid vs. pending

### The Solution
Payment Links provides a professional, automated payment workflow:
- **One-Click Creation** - Create payment requests in seconds
- **Automatic Emails** - System sends branded payment emails
- **Stripe Processing** - Secure, PCI-compliant payments
- **Status Tracking** - Real-time payment status updates
- **Financial Dashboard** - Track pending and collected amounts

---

## Key Features

### 1. Payment Link Creation
Create payment links with:
- Custom amount
- Description of service
- Client selection (platform or manual)
- Expiration period (7-90 days)
- Internal notes (private to you)

### 2. Email Delivery
- Professional branded emails
- One-click payment button
- Mobile-friendly design
- Resend capability
- Send count tracking

### 3. Status Tracking

| Status | Description |
|--------|-------------|
| **Draft** | Created but not sent |
| **Pending** | Sent, awaiting payment |
| **Paid** | Payment received |
| **Expired** | Past expiration date |
| **Cancelled** | Manually cancelled |

### 4. Financial Dashboard
Real-time metrics:
- Total links created
- Pending count and amount
- Paid count and total collected
- Conversion tracking

---

## Prerequisites

### Stripe Connect Setup
Before using Payment Links, you must complete Stripe onboarding:

1. Go to **Dashboard** tab in Chef Hub
2. Find the **Stripe Connect** section
3. Click **"Complete Stripe Onboarding"**
4. Follow Stripe's verification process
5. Once approved, Payment Links becomes active

> **Note**: Stripe may require identity verification, bank account details, and business information.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                   PAYMENT LINK WORKFLOW                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   1. CREATE LINK                                            │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ Amount: $150.00                                     │  │
│   │ Description: Weekly meal prep (Dec 2-8)             │  │
│   │ Client: Johnson Family                              │  │
│   │ Expires: 30 days                                    │  │
│   └─────────────────────────────────────────────────────┘  │
│                            │                                │
│                            ▼                                │
│   2. SEND EMAIL                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ To: sarah.j@email.com                               │  │
│   │ Subject: Payment Request from Chef Mike             │  │
│   │                                                     │  │
│   │ [Professional branded email with PAY NOW button]    │  │
│   └─────────────────────────────────────────────────────┘  │
│                            │                                │
│                            ▼                                │
│   3. CLIENT PAYS                                            │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ Stripe Checkout                                     │  │
│   │ • Credit/Debit card                                 │  │
│   │ • Apple Pay / Google Pay                            │  │
│   │ • Secure PCI-compliant                              │  │
│   └─────────────────────────────────────────────────────┘  │
│                            │                                │
│                            ▼                                │
│   4. PAYMENT CONFIRMED                                      │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ ✓ Status: PAID                                      │  │
│   │ ✓ Funds deposited to your Stripe account            │  │
│   │ ✓ Receipt sent to client                            │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Guide

### Step 1: Access Payment Links
1. Log in to Chef Hub
2. Click **"Payment Links"** in the left sidebar
3. You'll see your payment links dashboard

### Step 2: Create a Payment Link

1. Click **"+ Create Payment Link"** button
2. Fill in the form:

   **Amount ($)**
   - Enter the payment amount (minimum $0.50)
   - Example: `150.00`

   **Description**
   - Clear description of what this payment is for
   - Example: "Weekly meal prep service (Dec 2-8)"
   - This appears on the payment page

   **Select Client**
   - Choose from dropdown:
     - Manual Contacts (clients you added)
     - Platform Users (connected customers)
   - Client must have an email address

   **Expires In**
   - Choose expiration period:
     - 7 days
     - 14 days
     - 30 days (default)
     - 60 days
     - 90 days

   **Internal Notes** (optional)
   - Notes only you can see
   - Example: "Includes 5 dinners + snacks"

3. Click **"Create Payment Link"**

### Step 3: Send the Payment Link

#### Option A: Send via Email
1. Select the payment link from your list
2. Click **"Send Email"** button
3. System sends a branded email to the client
4. Track send count in the detail panel

#### Option B: Copy Link Manually
1. Select the payment link
2. Click **"Copy"** button next to the URL
3. Share via your preferred method (text, DM, etc.)

### Step 4: Track Payment Status

Monitor your payment links:
- **List View**: Shows all links with status badges
- **Detail Panel**: Full information when selected
- **Stats Cards**: Aggregate pending/paid amounts

### Step 5: Resend if Needed

If a client hasn't paid:
1. Select the payment link
2. Click **"Resend Email"**
3. A reminder email is sent
4. Send count updates

### Step 6: Cancel if Needed

To cancel a pending link:
1. Select the payment link
2. Click **"Cancel"** button
3. Confirm cancellation
4. Link is marked as cancelled

> **Note**: You cannot cancel a paid link. Contact Stripe support for refunds.

---

## Understanding the Interface

### Stats Dashboard

| Card | Description |
|------|-------------|
| **Total Links** | All-time count of payment links created |
| **Pending** | Links sent but not yet paid |
| **Paid** | Successfully completed payments |
| **Pending Amount** | Total $ awaiting payment |
| **Collected** | Total $ received |

### Payment Link Row

Each row shows:
- **Client Name** - Who the payment is from
- **Description** - Service description
- **Created Date** - When link was created
- **Amount** - Payment amount
- **Status Badge** - Current status (color-coded)

### Detail Panel

When a link is selected:
- **Status Badge** - Current status
- **Amount** - Large display of amount
- **Description** - Full description
- **Recipient Info** - Name, email, verification status
- **Payment URL** - Clickable link with copy button
- **Dates** - Created, expires, sent, paid
- **Internal Notes** - Your private notes
- **Actions** - Send/Resend, Cancel buttons

### Status Colors

| Status | Color | Meaning |
|--------|-------|---------|
| **Draft** | Gray | Not yet sent |
| **Pending** | Blue/Yellow | Awaiting payment |
| **Paid** | Green | Payment received |
| **Expired** | Red | Past expiration |
| **Cancelled** | Red | Manually cancelled |

---

## Email Verification

### Why It Matters
For manual contacts, email verification ensures:
- Emails aren't going to spam
- Client's email is valid
- Payment notifications will be received

### Verification Flow

1. When sending to an unverified manual contact:
   - System prompts: "Email not verified"
   - Option to send verification email first

2. Verification email sent to client:
   - "Please verify your email address"
   - One-click verification link
   - Valid for 24 hours

3. After verification:
   - Client email marked as verified
   - Future payment links send normally
   - Better email deliverability

### Verification Status
- ✓ **Verified** (green badge) - Email confirmed
- ⚠ **Not Verified** (yellow badge) - Needs verification

> **Note**: Platform users are automatically verified through their Hood United account.

---

## Best Practices

### 1. Clear Descriptions
Write descriptions your client will recognize:
- ✓ "Weekly meal prep (Dec 2-8) - 5 dinners"
- ✓ "In-home cooking service - Dec 15th"
- ✗ "Service" (too vague)
- ✗ "Payment" (doesn't help client remember)

### 2. Appropriate Expiration
Match expiration to your service timing:
- **7 days**: For immediate services
- **30 days**: Standard for most services
- **60-90 days**: For advance bookings

### 3. Use Internal Notes
Track important details:
- Service specifics
- Special requests fulfilled
- Discounts applied
- Related meal plan references

### 4. Verify Emails First
For new manual contacts:
1. Send verification email before first payment link
2. Wait for verification
3. Then send payment link
4. Better deliverability and tracking

### 5. Follow Up Professionally
For pending payments:
- Wait 3-5 days before first resend
- Send maximum 2-3 reminders
- Contact client directly if unresponsive

### 6. Track Your Metrics
Review your payment dashboard weekly:
- Collection rate (paid vs. total)
- Average payment time
- Pending amounts to follow up

---

## Troubleshooting

### "No email address available"

**Cause**: Client doesn't have an email on file.

**Solution**:
1. For manual contacts: Edit and add email
2. For platform users: Ask them to update their profile
3. Use Copy Link to share via another method

### Email marked as "Not Verified"

**Cause**: Manual contact's email hasn't been verified.

**Solution**:
1. Click to send verification email first
2. Ask client to check inbox (and spam)
3. After verification, send payment link

### Client didn't receive email

**Causes**:
- Email went to spam
- Typo in email address
- Email bounced

**Solutions**:
1. Ask client to check spam folder
2. Verify email address is correct
3. Use Copy Link to share directly
4. Resend the email

### Payment link expired

**Cause**: Passed the expiration date without payment.

**Solution**:
1. Create a new payment link
2. Optionally with a longer expiration
3. Send to the client

### Can't create payment link

**Causes**:
- Stripe onboarding incomplete
- Account restricted

**Solutions**:
1. Go to Dashboard tab
2. Check Stripe Connect status
3. Complete any pending requirements
4. Contact support if account is restricted

### Payment received but not showing

**Cause**: Webhook delay or processing time.

**Solutions**:
1. Wait 1-2 minutes and refresh
2. Check your Stripe dashboard directly
3. Contact support if persists

---

## Technical Details

### Data Model

```python
ChefPaymentLink:
    chef                  # FK to Chef
    customer              # FK to Customer (platform)
    lead                  # FK to Lead (manual contact)
    stripe_payment_link_id # Stripe PL ID
    stripe_price_id       # Stripe Price ID
    amount_cents          # Amount in cents
    currency              # Currency code (usd)
    description           # Public description
    internal_notes        # Private chef notes
    status                # draft, pending, paid, expired, cancelled
    payment_url           # Stripe checkout URL
    created_at            # Creation timestamp
    expires_at            # Expiration timestamp
    email_sent_at         # Last email sent
    email_send_count      # Number of emails sent
    paid_at               # Payment completion timestamp
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chefs/api/me/payment-links/` | GET | List payment links |
| `/chefs/api/me/payment-links/` | POST | Create payment link |
| `/chefs/api/me/payment-links/stats/` | GET | Get stats |
| `/chefs/api/me/payment-links/<id>/` | GET | Get link detail |
| `/chefs/api/me/payment-links/<id>/send/` | POST | Send email |
| `/chefs/api/me/payment-links/<id>/cancel/` | POST | Cancel link |
| `/chefs/api/leads/<id>/verify-email/` | POST | Send verification |

### Stripe Integration

Payment links use Stripe's:
- **Payment Links API** - For creating checkout URLs
- **Checkout Sessions** - For payment processing
- **Webhooks** - For status updates
- **Connect** - For chef payouts

### Fees

Standard Stripe processing fees apply:
- 2.9% + $0.30 per transaction (US)
- Fees may vary by country
- Platform fee (if applicable)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with Stripe integration |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*

