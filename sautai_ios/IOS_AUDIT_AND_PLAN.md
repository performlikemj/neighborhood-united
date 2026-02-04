# Sautai iOS App - Audit & Implementation Plan

**Created:** 2026-02-04  
**Branch:** main  
**Goal:** Mirror web functionality with native iOS experience

---

## Executive Summary

The iOS app has a solid foundation with ~9,000 lines of Swift code including:
- ✅ Complete design system matching brand guide
- ✅ Network layer with JWT auth and token refresh
- ✅ SSE streaming for Sous Chef AI
- ✅ Full UI structure for both Chef and Customer roles
- ⚠️ Several views have placeholder/incomplete implementations
- ⚠️ Some API endpoints don't match Django backend
- ❌ Missing several key features (onboarding, payments, meal plans)

---

## 1. Architecture Audit

### ✅ Core Infrastructure (Complete)

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| App Entry | `SautaiApp.swift` | ✅ Done | Role-based routing |
| Auth Manager | `Core/Auth/AuthManager.swift` | ✅ Done | JWT + Keychain |
| Keychain | `Core/Auth/KeychainService.swift` | ✅ Done | Secure storage |
| API Client | `Core/Network/APIClient.swift` | ⚠️ Partial | Some endpoints need fixes |
| Streaming | `Core/Network/StreamingClient.swift` | ⚠️ Partial | URL path issue |
| Design System | `Core/Design/` | ✅ Done | Colors, Typography, Tokens |

### ⚠️ API Client Issues

**1. StreamingClient URL Bug:**
```swift
// Current (WRONG):
let url = baseURL.appendingPathComponent("/chefs/api/me/sous-chef/stream/")
// This creates: http://localhost:8000/chefs/api/me/sous-chef/stream/
// Should use: URL(string: path, relativeTo: baseURL)
```

**2. Missing Endpoints in APIClient:**
- [ ] Meal plans for customers (`/meals/api/my-plans/`)
- [ ] Chef meal events (`/meals/api/chef-meal-events/`)
- [ ] Orders management (`/meals/api/chef-meal-orders/`)
- [ ] Stripe payment flows (`/meals/api/process-chef-meal-payment/`)
- [ ] Leads management (`/chefs/api/me/leads/`)
- [ ] Prep plans (`/chefs/api/me/prep-plans/`)
- [ ] Proactive insights (`/chefs/api/me/insights/`)
- [ ] Telegram linking (`/chefs/api/telegram/`)
- [ ] Onboarding (`/chefs/api/onboarding/`)

**3. Endpoint Mismatches:**
```swift
// iOS expects:
"/chefs/api/public/"  // Returns PaginatedResponse

// Django returns:
// Different format - need to verify serializer output
```

---

## 2. Views Audit

### Chef Views

| View | File | API Connected | Functional | Issues |
|------|------|---------------|------------|--------|
| Dashboard | `Chef/Dashboard/ChefDashboardView.swift` | ⚠️ | ⚠️ | Dashboard API response format |
| Clients | `Chef/Clients/ClientsListView.swift` | ⚠️ | ⚠️ | Pagination, detail view |
| Sous Chef | `Chef/SousChef/SousChefView.swift` | ⚠️ | ⚠️ | StreamingClient URL bug |
| Meal Plans | `Chef/MealPlanning/MealPlansListView.swift` | ❌ | ❌ | No API connection |
| Settings | `Settings/SettingsView.swift` | ⚠️ | ⚠️ | Logout works, rest placeholder |

### Customer Views

| View | File | API Connected | Functional | Issues |
|------|------|---------------|------------|--------|
| Dashboard | `Customer/Dashboard/CustomerDashboardView.swift` | ⚠️ | ⚠️ | Missing orders API |
| Chef Discovery | `Customer/ChefDiscovery/ChefDiscoveryView.swift` | ⚠️ | ⚠️ | API format mismatch |
| Chef Profile | `Customer/ChefDiscovery/ChefProfileView.swift` | ⚠️ | ⚠️ | Incomplete |
| Messages | `Messaging/ConversationsListView.swift` | ❌ | ❌ | No API endpoints |
| Chat | `Messaging/ChatView.swift` | ❌ | ❌ | No API endpoints |

### Auth Views

| View | File | API Connected | Functional | Issues |
|------|------|---------------|------------|--------|
| Login | `Auth/LoginView.swift` | ✅ | ✅ | Works |
| Register | `Auth/RegisterView.swift` | ⚠️ | ⚠️ | Missing email verification |
| Forgot Password | `Auth/ForgotPasswordView.swift` | ⚠️ | ❌ | API not connected |

---

## 3. Django API Mapping

### Authentication (`/custom_auth/api/`)
| Endpoint | iOS Method | Status |
|----------|------------|--------|
| `POST /login/` | `login()` | ✅ |
| `POST /register/` | `register()` | ✅ |
| `POST /token/refresh/` | `refreshToken()` | ✅ |
| `GET /user_details/` | `getUserProfile()` | ✅ |
| `POST /switch_role/` | `switchRole()` | ✅ |
| `POST /password_reset_request/` | - | ❌ Missing |
| `POST /resend-activation-link/` | - | ❌ Missing |

### Chef APIs (`/chefs/api/me/`)
| Endpoint | iOS Method | Status |
|----------|------------|--------|
| `GET /dashboard/` | `getChefDashboard()` | ✅ |
| `GET /clients/` | `getClients()` | ✅ |
| `GET /clients/:id/` | `getClient()` | ✅ |
| `GET /leads/` | - | ❌ Missing |
| `POST/GET /leads/:id/` | - | ❌ Missing |
| `GET /sous-chef/stream/` | StreamingClient | ⚠️ URL bug |
| `GET /sous-chef/history/` | `getSousChefHistory()` | ✅ |
| `POST /sous-chef/new-conversation/` | `startSousChefConversation()` | ✅ |
| `GET /insights/` | - | ❌ Missing (proactive) |
| `GET /prep-plans/` | - | ❌ Missing |
| `GET /revenue/` | - | ❌ Missing |
| `POST /telegram/generate-link/` | - | ❌ Missing |

### Customer APIs (`/customer_dashboard/api/`)
| Endpoint | iOS Method | Status |
|----------|------------|--------|
| `GET /my-chefs/` | `getMyChefs()` | ✅ |
| `GET /my-chefs/:id/` | - | ❌ Missing |
| `GET /chat_with_gpt/` | - | ❌ Missing |
| `GET /meal_plans/` | - | ❌ Missing |

### Public Chef APIs (`/chefs/api/public/`)
| Endpoint | iOS Method | Status |
|----------|------------|--------|
| `GET /` | `getPublicChefs()` | ⚠️ Check format |
| `GET /:id/` | `getChefProfile()` | ⚠️ Check format |
| `GET /:id/serves-my-area/` | `checkChefServesArea()` | ✅ |

### Meals APIs (`/meals/api/`)
| Endpoint | iOS Method | Status |
|----------|------------|--------|
| `GET /my-plans/` | - | ❌ Missing |
| `GET /my-plans/current/` | - | ❌ Missing |
| `GET /chef-meal-orders/` | - | ❌ Missing |
| `POST /process-chef-meal-payment/:id/` | - | ❌ Missing |

### Messaging APIs (`/messaging/api/`)
| Endpoint | iOS Method | Status |
|----------|------------|--------|
| `GET /conversations/` | `getConversations()` | ✅ (untested) |
| `GET /conversations/:id/` | `getMessages()` | ✅ (untested) |
| `POST /conversations/:id/send/` | `sendMessage()` | ✅ (untested) |

---

## 4. Implementation Plan

### Phase 1: Critical Fixes (Week 1)
**Priority: Get existing features working**

1. **Fix StreamingClient URL** 🔴
   ```swift
   // Change from:
   let url = baseURL.appendingPathComponent("/chefs/api/me/sous-chef/stream/")
   // To:
   let url = URL(string: "/chefs/api/me/sous-chef/stream/", relativeTo: baseURL)!
   ```

2. **Verify API Response Formats** 🔴
   - Test `/chefs/api/me/dashboard/` response matches `ChefDashboard` model
   - Test `/chefs/api/public/` response matches `PublicChef` model
   - Test `/chefs/api/me/clients/` pagination format

3. **Add Error States to All Views** 🟡
   - Connection errors
   - Auth errors
   - Empty states

4. **Test Authentication Flow** 🔴
   - Login → Dashboard
   - Token refresh
   - Logout
   - Session restore

### Phase 2: Complete Chef Features (Weeks 2-3)
**Priority: Chef app MVP**

1. **Leads Management** 🔴
   - Add `Lead` model (exists)
   - Add API endpoints to `APIClient`
   - Create `LeadsListView.swift`
   - Create `LeadDetailView.swift`

2. **Prep Plans** 🟡
   - Add `PrepPlan` model
   - Add API endpoints
   - Create `PrepPlansView.swift`
   - Shopping list generation

3. **Meal Events (Chef Creating Meals)** 🔴
   - Add `ChefMealEvent` model
   - CRUD operations
   - Calendar integration

4. **Orders Management** 🔴
   - View incoming orders
   - Confirm/reject orders
   - Order status updates

5. **Proactive Insights** 🟡
   - Add `ProactiveInsight` model
   - Display insights on dashboard
   - Action buttons

### Phase 3: Complete Customer Features (Weeks 4-5)
**Priority: Customer app MVP**

1. **Onboarding Flow** 🔴
   - Dietary preferences
   - Allergies
   - Address/location
   - Household setup

2. **Chef Profile & Ordering** 🔴
   - Complete `ChefProfileView`
   - Menu display
   - Add to cart
   - Checkout flow

3. **Stripe Payments** 🔴
   - Integrate Stripe iOS SDK
   - Payment sheet
   - Save payment methods
   - Order payment

4. **Meal Plans (Customer View)** 🟡
   - View current plan
   - Plan history
   - Suggestions

5. **AI Assistant (Customer)** 🟡
   - Different from chef Sous Chef
   - Use `chat_with_gpt` endpoint
   - Recipe suggestions

### Phase 4: Messaging & Real-time (Week 6)
**Priority: Communication**

1. **Conversations** 🔴
   - List all conversations
   - Unread counts
   - Start new conversation

2. **Chat View** 🔴
   - Message history
   - Send messages
   - Real-time updates (polling or WebSocket)

3. **Push Notifications** 🟡
   - APNs setup
   - Message notifications
   - Order updates

### Phase 5: Polish & Testing (Week 7-8)
**Priority: App Store ready**

1. **Offline Support** 🟡
   - SwiftData caching
   - Queue offline actions
   - Sync on reconnect

2. **Deep Linking** 🟡
   - Universal links
   - Chef profile sharing
   - Order confirmations

3. **Accessibility** 🔴
   - VoiceOver support
   - Dynamic type
   - Reduce motion

4. **Unit Tests** 🔴
   - Model tests
   - API client tests
   - View model tests

5. **UI Tests** 🟡
   - Login flow
   - Order flow
   - Critical paths

---

## 5. Immediate Actions

### Today
1. [ ] Fix `StreamingClient` URL bug
2. [ ] Add missing API endpoints to `APIClient.swift`
3. [ ] Run Django server locally and test iOS login

### This Week
1. [ ] Verify all model <-> API serializer mappings
2. [ ] Complete `ChefProfileView.swift` 
3. [ ] Add password reset flow
4. [ ] Add email verification handling

### Files to Create

```
sautai_ios/
├── Core/
│   ├── Models/
│   │   ├── Lead/
│   │   │   └── Lead.swift              # Move from Chef.swift
│   │   ├── PrepPlan/
│   │   │   └── PrepPlan.swift
│   │   ├── MealEvent/
│   │   │   └── MealEvent.swift
│   │   └── Insight/
│   │       └── ProactiveInsight.swift
│   └── Services/
│       └── StripeService.swift
├── Features/
│   ├── Chef/
│   │   ├── Leads/
│   │   │   ├── LeadsListView.swift
│   │   │   └── LeadDetailView.swift
│   │   ├── PrepPlans/
│   │   │   ├── PrepPlansListView.swift
│   │   │   └── PrepPlanDetailView.swift
│   │   └── MealEvents/
│   │       ├── MealEventsListView.swift
│   │       └── CreateMealEventView.swift
│   ├── Customer/
│   │   ├── Onboarding/
│   │   │   ├── OnboardingView.swift
│   │   │   ├── DietaryPreferencesView.swift
│   │   │   ├── AllergiesView.swift
│   │   │   └── AddressSetupView.swift
│   │   ├── MealPlans/
│   │   │   ├── MealPlansView.swift
│   │   │   └── MealPlanDetailView.swift
│   │   ├── Cart/
│   │   │   └── CartView.swift
│   │   └── Checkout/
│   │       └── CheckoutView.swift
│   └── Shared/
│       └── AIAssistantView.swift
└── Resources/
    └── Fonts/                          # Add Poppins, Kalam
```

---

## 6. Testing Checklist

### Before Each PR
- [ ] App launches without crash
- [ ] Login flow works
- [ ] Role switching works
- [ ] No memory leaks (Instruments)
- [ ] Dark mode renders correctly
- [ ] All text is localization-ready

### Before App Store
- [ ] All critical flows tested on device
- [ ] Network error handling works
- [ ] Offline graceful degradation
- [ ] Accessibility audit passed
- [ ] Performance profiling done
- [ ] App Store screenshots ready
- [ ] Privacy policy updated
- [ ] App description written

---

## 7. Dependencies to Add

```swift
// Package.swift or via Xcode

dependencies: [
    // Stripe
    .package(url: "https://github.com/stripe/stripe-ios", from: "23.0.0"),
    
    // Image loading (optional, can use AsyncImage)
    // .package(url: "https://github.com/kean/Nuke", from: "12.0.0"),
    
    // Keychain (already using custom implementation, could use)
    // .package(url: "https://github.com/kishikawakatsumi/KeychainAccess", from: "4.0.0"),
]
```

---

## Notes

- **No SQLite/CoreData** - Using SwiftData (iOS 17+)
- **No Combine** - Using async/await throughout
- **No third-party UI libs** - Pure SwiftUI
- **Minimum iOS 17** - Allows @Observable, SwiftData, etc.

---

*Last updated: 2026-02-04*
