# sautai iOS Implementation Plan

## Overview
This plan outlines the work needed to properly connect the iOS app to the Django backend.

---

## Phase 1: Fix Model Mismatches ✅ (Partially Done)

### Completed:
- [x] Lead model - aligned with Django `LeadListSerializer`
- [x] LeadInteraction model - aligned with Django `ClientNoteSerializer`
- [x] Client model - aligned with Django `ClientListItemSerializer`

### To Fix:
- [ ] **RevenueStats** - Django returns `Decimal` numbers, iOS expects `String`
- [ ] **TopService** - `serviceType` is optional in Django, required in iOS

---

## Phase 2: Implement Dashboard Navigation

### Quick Actions (currently `// TODO`):
1. **"New Order"** → Navigate to order creation flow
2. **"Add Client"** → Open add client sheet
3. **"Schedule"** → Navigate to calendar/scheduling view

### Stats Cards (make tappable):
1. **Clients count** → Navigate to Clients tab
2. **Upcoming orders** → Navigate to orders list
3. **Completed orders** → Navigate to orders with filter

---

## Phase 3: Fix SousChef AI Chat

### Issues:
1. Errors may be swallowed silently
2. Need better loading states
3. Need to show actual error messages in UI

### Fixes:
1. Add console logging for debugging
2. Show user-friendly error alerts
3. Implement retry mechanism

---

## Phase 4: Add Missing Features

### Add Client Flow:
1. Create `AddClientView` sheet
2. API endpoint: `POST /chefs/api/me/leads/` for manual clients
3. Or search existing users to connect with

### Navigation Structure:
- Dashboard → Quick actions navigate to correct tabs
- Stats cards → Tappable with navigation

---

## Phase 5: API Integration Testing

### Test Each Endpoint:
1. `GET /chefs/api/me/dashboard/` - Dashboard data
2. `GET /chefs/api/me/clients/` - Client list
3. `GET /chefs/api/me/leads/` - Leads list
4. `POST /chefs/api/me/sous-chef/stream/` - AI chat

---

## Files to Modify

1. **Chef.swift** - Fix RevenueStats and TopService models
2. **ChefDashboardView.swift** - Implement quick action navigation
3. **SousChefView.swift** - Better error handling
4. **SautaiApp.swift** - Ensure tab navigation works
5. **APIClient.swift** - Add debug logging

---

## Estimated Timeline

| Phase | Description | Time |
|-------|-------------|------|
| 1 | Fix model mismatches | 30 min |
| 2 | Dashboard navigation | 45 min |
| 3 | SousChef fixes | 30 min |
| 4 | Add client flow | 45 min |
| 5 | Testing | 30 min |

**Total: ~3 hours**
