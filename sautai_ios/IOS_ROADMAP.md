# Sautai iOS App - Feature Parity Roadmap

> **Django Backend**: ~400 endpoints | **iOS App Current Coverage**: ~5%
>
> Last Updated: February 2026

---

## Executive Summary

The Django backend is a sophisticated, full-featured platform with AI-powered meal planning, CRM, real-time messaging, and payment processing. The iOS app currently implements basic authentication, dashboard viewing, and the Sous Chef AI chat. This roadmap outlines the path to full feature parity.

---

## Progress Legend

- ⬜ **Not Started** - No implementation
- 🟡 **In Progress** - Partial implementation
- ✅ **Complete** - Fully implemented and tested
- 🔴 **Blocked** - Waiting on dependencies
- ⏭️ **Deferred** - Planned for later phase

---

## Phase 1: Foundation (Current Sprint)
*Goal: Core authentication, navigation, and data display*

### 1.1 Authentication & Session Management
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| Login | ✅ | `AuthManager.swift` | `POST /auth/api/login/` | Working |
| Token Refresh | ✅ | `AuthManager.swift` | `POST /auth/api/token/refresh/` | Working |
| Logout | ✅ | `AuthManager.swift` | `POST /auth/api/logout/` | Blacklists token on server |
| User Details | ✅ | `AuthManager.swift` | `GET /auth/api/user_details/` | Working |
| Password Reset Request | ✅ | `ForgotPasswordView.swift` | `POST /auth/api/password_reset_request/` | API connected |
| Change Password | ✅ | `ChangePasswordView.swift` | `POST /auth/api/change_password/` | With validation & strength indicator |
| Registration | ✅ | `RegisterView.swift` | `POST /auth/api/register/` | With validation |
| Email Verification | 🟡 | `RegisterView.swift` | `POST /auth/api/register/verify-email/` | Shows success message |
| Delete Account | ✅ | `DeleteAccountView.swift` | `POST /auth/api/delete_account/` | With confirmation flow |
| Role Switching | ✅ | `SettingsView.swift` | `POST /auth/api/switch_role/` | Working |

**Implementation Plan:**
```
[x] Create LogoutView with token blacklist ✅ (AuthManager.logout() calls API)
[x] Add PasswordResetView flow ✅ (ForgotPasswordView calls API)
[x] Create RegistrationView with validation ✅ (Email, username, password strength)
[x] Add email verification handling ✅ (Success message directs to email)
[x] Test: Login → Logout → Login cycle ✅ (Unit tests added)
[x] Test: Password reset email flow ✅ (API connected)
```

---

### 1.2 Chef Dashboard
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| Dashboard Summary | 🟡 | `ChefDashboardView.swift` | `GET /chefs/api/me/dashboard/` | Displays but models need work |
| Revenue Stats | 🟡 | `Chef.swift` | Part of dashboard | Fixed Decimal parsing |
| Top Services | 🟡 | `Chef.swift` | Part of dashboard | Made serviceType optional |
| Recent Orders | ✅ | `ChefDashboardView.swift` | Part of dashboard | OrderRowView implemented |
| Upcoming Events | ✅ | `ChefDashboardView.swift` | Part of dashboard | EventRowView implemented |
| Quick Actions | ✅ | `ChefDashboardView.swift` | N/A (navigation) | Implemented |

**Implementation Plan:**
```
[x] Add RecentOrdersSection to dashboard ✅
[x] Add UpcomingEventsSection to dashboard ✅
[x] Create OrderRowView component ✅
[x] Create EventRowView component ✅
[x] Add pull-to-refresh ✅ (refreshable modifier)
[ ] Test: Dashboard loads all sections
[ ] Test: Tapping items navigates correctly
```

---

### 1.3 Client Management (CRM)
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Clients | ✅ | `ClientsListView.swift` | `GET /chefs/api/me/clients/` | Full list with search |
| Client Detail | ✅ | `ClientDetailView` (in ClientsListView) | `GET /chefs/api/me/clients/{id}/` | Full detail view |
| Client Notes | ✅ | `ClientDetailView` | `GET /chefs/api/me/clients/{id}/notes/` | Notes list |
| Add Note | ✅ | `AddClientNoteView` | `POST /chefs/api/me/clients/{id}/notes/` | Add note sheet |
| Client Receipts | ✅ | `ClientsListView.swift` | `GET /chefs/api/me/clients/{id}/receipts/` | With totals summary |
| Client Orders | ⬜ | - | Via dashboard | |
| Search/Filter | ✅ | `ClientsListView.swift` | Query params | Search implemented |

**Implementation Plan:**
```
[x] Create ClientDetailView ✅ (Full detail with stats, actions, notes)
[x] Add ClientNotesSection ✅ (Notes list in detail view)
[x] Create AddNoteSheet ✅ (AddClientNoteView)
[x] Add client search functionality ✅ (Search in ClientsListView)
[x] Create ClientReceiptsView ✅ (Receipts section with totals)
[ ] Test: Navigate to client → View notes → Add note
[ ] Test: Search filters correctly
```

---

### 1.4 Lead Management (CRM)
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Leads | 🟡 | `LeadsListView.swift` | `GET /chefs/api/me/leads/` | Basic list works |
| Lead Detail | ✅ | `LeadDetailView.swift` | `GET /chefs/api/me/leads/{id}/` | Full detail view |
| Add Lead | ✅ | `AddLeadView` (in LeadsListView) | `POST /chefs/api/me/leads/` | Full form |
| Edit Lead | ✅ | `EditLeadView` (in LeadDetailView) | `PATCH /chefs/api/me/leads/{id}/` | All fields editable |
| Delete Lead | ✅ | `LeadsListView.swift` | `DELETE /chefs/api/me/leads/{id}/` | Swipe to delete |
| Lead Interactions | ✅ | `LeadDetailView.swift` | `GET /chefs/api/me/leads/{id}/interactions/` | Shows list |
| Add Interaction | ✅ | `AddInteractionView` (in LeadDetailView) | `POST /chefs/api/me/leads/{id}/interactions/` | Full form |
| Lead Household | ✅ | `LeadDetailView.swift` | `GET /chefs/api/me/leads/{id}/household/` | With dietary & allergy display |
| Status Filter | 🟡 | `LeadsListView.swift` | Query params | Working |
| Send Verification | ⬜ | - | `POST /chefs/api/me/leads/{id}/send-verification/` | |

**Implementation Plan:**
```
[x] Create EditLeadView ✅ (Full edit with all fields)
[x] Create AddInteractionSheet ✅ (AddInteractionView implemented)
[x] Add household member section to lead detail ✅
[ ] Implement lead verification flow
[x] Add more lead fields (budget, priority indicator) ✅ (In EditLeadView)
[ ] Test: Full lead lifecycle (add → edit → interact → convert)
```

---

### 1.5 Sous Chef AI Assistant
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| Stream Messages | ✅ | `StreamingClient.swift` | `POST /chefs/api/me/sous-chef/stream/` | Working with client_type |
| Chat UI | ✅ | `SousChefView.swift` | N/A | Working |
| Markdown Rendering | ✅ | `SousChefView.swift` | N/A | Using AttributedString |
| New Conversation | ✅ | `SousChefView.swift` | `POST /chefs/api/me/sous-chef/new-conversation/` | Reset button calls API |
| Conversation History | ⬜ | - | `GET /chefs/api/me/sous-chef/history/{type}/{id}/` | |
| Family Context | ⬜ | - | `GET /chefs/api/me/sous-chef/context/{type}/{id}/` | |
| Suggestions | ⬜ | - | `POST /chefs/api/me/sous-chef/suggest/` | |
| Scaffold Generate | ⬜ | - | `POST /chefs/api/me/sous-chef/scaffold/generate/` | |
| Scaffold Execute | ⬜ | - | `POST /chefs/api/me/sous-chef/scaffold/execute/` | |

**Implementation Plan:**
```
[x] Call new-conversation API when tapping reset button ✅
[ ] Add conversation history persistence
[ ] Create family/client context selector
[ ] Show AI suggestions as quick action chips
[ ] Test: Full conversation with context switching
```

---

## Phase 2: Core Business Features
*Goal: Orders, meals, and service management*

### 2.1 Order Management
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Orders | ⬜ | - | `GET /meals/api/chef-meal-orders/` | |
| Order Detail | ⬜ | - | `GET /meals/api/chef-meal-orders/{id}/` | |
| Confirm Order | ⬜ | - | `POST /meals/api/chef-meal-orders/{id}/confirm/` | |
| Cancel Order | ⬜ | - | `POST /meals/api/chef-meal-orders/{id}/cancel/` | |
| Adjust Quantity | ⬜ | - | `POST /meals/api/chef-meal-orders/{id}/adjust-quantity/` | |
| Order Calendar | ⬜ | - | `GET /meals/api/chef-calendar/` | |

**Implementation Plan:**
```
[ ] Create OrdersListView
[ ] Create OrderDetailView with actions
[ ] Add order status badges and colors
[ ] Create OrderCalendarView
[ ] Implement push notifications for new orders
[ ] Test: Receive order → Confirm → Complete flow
```

---

### 2.2 Meal Events (Meal Shares)
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Events | ⬜ | - | `GET /meals/api/chef-meal-events/` | |
| Create Event | ⬜ | - | `POST /meals/api/chef-meal-events/` | |
| Update Event | ⬜ | - | `POST /meals/api/chef-meal-events/{id}/update/` | |
| Cancel Event | ⬜ | - | `POST /meals/api/chef-meal-events/{id}/cancel/` | |
| Duplicate Event | ⬜ | - | `POST /meals/api/chef-meal-events/{id}/duplicate/` | |
| Event Orders | ⬜ | - | `GET /meals/api/chef-meal-events/{id}/order/` | |

**Implementation Plan:**
```
[ ] Create MealEventsListView
[ ] Create MealEventDetailView
[ ] Create AddMealEventView with date picker
[ ] Add event management actions
[ ] Test: Create event → Get orders → Complete
```

---

### 2.3 Meals & Dishes
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Meals | ⬜ | - | `GET /meals/api/chef/meals/` | |
| Create Meal | ⬜ | - | `POST /meals/api/chef/meals/` | |
| Update Meal | ⬜ | - | `PUT /meals/api/chef/meals/{id}/update/` | |
| List Dishes | ⬜ | - | `GET /meals/api/dishes/` | |
| Create Dish | ⬜ | - | `POST /meals/api/create-chef-dish/` | |
| Update Dish | ⬜ | - | `PUT /meals/api/dishes/{id}/update/` | |
| Delete Dish | ⬜ | - | `DELETE /meals/api/dishes/{id}/delete/` | |

**Implementation Plan:**
```
[ ] Create KitchenView (meals/dishes hub)
[ ] Create MealDetailView
[ ] Create DishDetailView
[ ] Create AddMealView with dish picker
[ ] Create AddDishView with ingredients
[ ] Test: Create dish → Add to meal → Publish
```

---

### 2.4 Ingredients
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Ingredients | ⬜ | - | `GET /meals/api/ingredients/` | |
| Search Ingredients | ⬜ | - | `GET /meals/api/search_ingredients/` | |
| Create Ingredient | ⬜ | - | `POST /meals/api/chef/ingredients/` | |
| Update Ingredient | ⬜ | - | `PUT /meals/api/chef/ingredients/{id}/` | |
| Delete Ingredient | ⬜ | - | `DELETE /meals/api/chef/ingredients/{id}/delete/` | |

**Implementation Plan:**
```
[ ] Create IngredientsListView
[ ] Add ingredient search with autocomplete
[ ] Create AddIngredientView
[ ] Test: Search → Select → Add to dish
```

---

### 2.5 Service Offerings
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Offerings | ⬜ | - | `GET /services/offerings/` | |
| Create Offering | ⬜ | - | `POST /services/offerings/` | |
| Update Offering | ⬜ | - | `PUT /services/offerings/{id}/` | |
| Delete Offering | ⬜ | - | `DELETE /services/offerings/{id}/delete/` | |
| Price Tiers | ⬜ | - | `POST /services/offerings/{id}/tiers/` | |

**Implementation Plan:**
```
[ ] Create ServicesListView
[ ] Create ServiceDetailView
[ ] Create AddServiceView with tier pricing
[ ] Test: Create service → Add tiers → Publish
```

---

## Phase 3: Advanced Features
*Goal: Collaborative planning, prep, and analytics*

### 3.1 Collaborative Meal Plans
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Client Plans | ⬜ | - | `GET /chefs/api/me/clients/{id}/plans/` | |
| Plan Detail | ⬜ | - | `GET /chefs/api/me/plans/{id}/` | |
| Publish Plan | ⬜ | - | `POST /chefs/api/me/plans/{id}/publish/` | |
| Add Plan Day | ⬜ | - | `POST /chefs/api/me/plans/{id}/days/` | |
| Add Plan Item | ⬜ | - | `POST /chefs/api/me/plans/{id}/days/{day_id}/items/` | |
| View Suggestions | ⬜ | - | `GET /chefs/api/me/plans/{id}/suggestions/` | |
| Respond to Suggestion | ⬜ | - | `POST /chefs/api/me/suggestions/{id}/respond/` | |
| AI Generate Meals | ⬜ | - | `POST /chefs/api/me/plans/{id}/generate/` | |

**Implementation Plan:**
```
[ ] Create MealPlansListView
[ ] Create MealPlanDetailView with calendar
[ ] Create PlanDayView with meal slots
[ ] Add AI generation integration
[ ] Create SuggestionResponseSheet
[ ] Test: Create plan → Generate meals → Client suggests → Respond
```

---

### 3.2 Prep Planning
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Prep Plans | ⬜ | - | `GET /chefs/api/me/prep-plans/` | |
| Prep Plan Detail | ⬜ | - | `GET /chefs/api/me/prep-plans/{id}/` | |
| Shopping List | ⬜ | - | `GET /chefs/api/me/prep-plans/{id}/shopping-list/` | |
| Mark Purchased | ⬜ | - | `POST /chefs/api/me/prep-plans/{id}/mark-purchased/` | |
| Quick Generate | ⬜ | - | `POST /chefs/api/me/prep-plans/quick-generate/` | |
| Live Commitments | ⬜ | - | `GET /chefs/api/me/prep-plans/live/commitments/` | |

**Implementation Plan:**
```
[ ] Create PrepPlanningView
[ ] Create ShoppingListView with checkboxes
[ ] Add quick generation from orders
[ ] Create live commitments dashboard
[ ] Test: Orders → Generate prep → Shopping list → Mark done
```

---

### 3.3 Notifications
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Notifications | ⬜ | - | `GET /chefs/api/me/notifications/` | |
| Unread Count | ⬜ | - | `GET /chefs/api/me/notifications/unread-count/` | |
| Mark Read | ⬜ | - | `POST /chefs/api/me/notifications/{id}/read/` | |
| Mark All Read | ⬜ | - | `POST /chefs/api/me/notifications/mark-all-read/` | |
| Dismiss | ⬜ | - | `POST /chefs/api/me/notifications/{id}/dismiss/` | |
| Push Notifications | ⬜ | - | APNs integration | |

**Implementation Plan:**
```
[ ] Create NotificationsView
[ ] Add notification badge to tab bar
[ ] Implement push notification handling
[ ] Add notification preferences in settings
[ ] Test: Receive notification → Tap → Navigate to source
```

---

### 3.4 Messaging
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Conversations | ⬜ | - | `GET /messaging/api/conversations/` | |
| Get Conversation | ⬜ | - | `GET /messaging/api/conversations/{id}/` | |
| Send Message | ⬜ | - | `POST /messaging/api/conversations/{id}/send/` | |
| Unread Counts | ⬜ | - | `GET /messaging/api/unread-counts/` | |
| Mark Read | ⬜ | - | `POST /messaging/api/conversations/{id}/read/` | |
| WebSocket | ⬜ | - | WebSocket connection | Real-time |

**Implementation Plan:**
```
[ ] Create ConversationsListView
[ ] Create ChatView with message bubbles
[ ] Implement WebSocket for real-time
[ ] Add typing indicators
[ ] Test: Send message → Receive reply → Real-time updates
```

---

### 3.5 Reviews & Ratings
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| View My Reviews | ⬜ | - | `GET /reviews/my_reviews/` | |
| View Chef Reviews | ⬜ | - | `GET /reviews/chef/{id}/reviews/` | |
| Reply to Review | ⬜ | - | - | May need API |

**Implementation Plan:**
```
[ ] Create ReviewsListView
[ ] Add review display to profile
[ ] Test: View reviews
```

---

## Phase 4: Profile & Settings
*Goal: Complete profile management and app settings*

### 4.1 Chef Profile
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| View Profile | ⬜ | - | `GET /chefs/api/me/chef/profile/` | |
| Update Profile | ⬜ | - | `POST /chefs/api/me/chef/profile/update/` | |
| Photo Gallery | ⬜ | - | `GET /chefs/api/{username}/photos/` | |
| Upload Photo | ⬜ | - | `POST /chefs/api/me/chef/photos/` | |
| Delete Photo | ⬜ | - | `DELETE /chefs/api/me/chef/photos/{id}/` | |
| Set Break Status | ⬜ | - | `POST /chefs/api/me/chef/break/` | |
| Set Live Status | ⬜ | - | `POST /chefs/api/me/chef/live/` | |

**Implementation Plan:**
```
[ ] Create ChefProfileView
[ ] Create EditProfileView
[ ] Create PhotoGalleryView with upload
[ ] Add break/live toggle
[ ] Test: Update profile → Upload photo → Toggle status
```

---

### 4.2 Service Areas
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| View Service Areas | ⬜ | - | `GET /local_chefs/api/chef/service-areas/` | |
| Add Area | ⬜ | - | `POST /local_chefs/api/chef/service-areas/add/` | |
| Remove Area | ⬜ | - | `DELETE /local_chefs/api/chef/service-areas/{id}/remove/` | |
| Add Postal Codes | ⬜ | - | `POST /local_chefs/api/chef/service-areas/postal-codes/add/` | |

**Implementation Plan:**
```
[ ] Create ServiceAreasView with map
[ ] Create AddAreaSheet with search
[ ] Test: Add area → Add postal codes → View on map
```

---

### 4.3 Verification & Compliance
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| View Documents | ⬜ | - | `GET /chefs/api/me/documents/` | |
| Upload Document | ⬜ | - | Document upload | |
| Verification Status | ⬜ | - | `GET /chefs/api/me/documents/status/` | |
| Schedule Meeting | ⬜ | - | `POST /chefs/api/me/verification-meeting/schedule/` | |

**Implementation Plan:**
```
[ ] Create VerificationView
[ ] Add document upload with camera
[ ] Show verification status badges
[ ] Test: Upload document → Schedule meeting
```

---

### 4.4 Settings
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| App Settings | ⬜ | `SettingsView.swift` | - | Basic shell exists |
| Notifications Prefs | ⬜ | - | Proactive settings | |
| Telegram Link | ⬜ | - | `POST /chefs/api/telegram/generate-link/` | |
| Workspace Settings | ⬜ | - | `GET /chefs/api/me/workspace/` | |

**Implementation Plan:**
```
[ ] Expand SettingsView with sections
[ ] Add notification preferences
[ ] Add Telegram linking flow
[ ] Add logout confirmation
[ ] Test: Change settings → Verify persistence
```

---

## Phase 5: Payments & Commerce
*Goal: Full payment integration*

### 5.1 Stripe Integration
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| Account Status | ⬜ | - | `GET /meals/api/stripe-account-status/` | |
| Create Account Link | ⬜ | - | `POST /meals/api/stripe-account-link/` | |
| Process Payment | ⬜ | - | `POST /meals/api/process-chef-meal-payment/{id}/` | |
| Payment Status | ⬜ | - | `GET /meals/api/order-payment-status/{id}/` | |

**Implementation Plan:**
```
[ ] Create PaymentSetupView
[ ] Add Stripe SDK integration
[ ] Create payment processing flow
[ ] Test: Setup account → Process payment → Verify
```

---

### 5.2 Payment Links
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Payment Links | ⬜ | - | `GET /chefs/api/me/payment-links/` | |
| Create Link | ⬜ | - | `POST /chefs/api/me/payment-links/` | |
| Send Link | ⬜ | - | `POST /chefs/api/me/payment-links/{id}/send/` | |
| Link Stats | ⬜ | - | `GET /chefs/api/me/payment-links/stats/` | |

**Implementation Plan:**
```
[ ] Create PaymentLinksView
[ ] Create CreatePaymentLinkView
[ ] Add share sheet for sending links
[ ] Test: Create link → Send → Track payment
```

---

### 5.3 Receipts
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Receipts | ⬜ | - | `GET /chefs/api/me/receipts/` | |
| Receipt Detail | ⬜ | - | `GET /chefs/api/me/receipts/{id}/` | |
| Receipt Stats | ⬜ | - | `GET /chefs/api/me/receipts/stats/` | |

**Implementation Plan:**
```
[ ] Create ReceiptsListView
[ ] Create ReceiptDetailView
[ ] Add PDF export option
[ ] Test: View receipts → Export PDF
```

---

## Testing Checklist

### Unit Tests
```
[ ] AuthManager tests
[ ] APIClient tests
[ ] StreamingClient tests
[ ] Model decoding tests
[ ] ViewModel tests
```

### Integration Tests
```
[ ] Login → Dashboard → Logout flow
[ ] CRUD operations for all entities
[ ] Sous Chef conversation flow
[ ] Payment processing flow
```

### UI Tests
```
[ ] Navigation flow tests
[ ] Form validation tests
[ ] Error state tests
[ ] Loading state tests
```

---

## Technical Debt & Improvements

### High Priority
- [ ] Add proper error handling to all API calls
- [ ] Implement offline mode with CoreData
- [ ] Add proper loading states everywhere
- [ ] Implement retry logic for failed requests

### Medium Priority
- [ ] Add analytics tracking
- [ ] Implement deep linking
- [ ] Add haptic feedback
- [ ] Improve accessibility

### Low Priority
- [ ] Add widget support
- [ ] Implement Siri shortcuts
- [ ] Add Apple Watch companion

---

## API Client Methods Needed

```swift
// Phase 1
func logout() async throws
func resetPassword(email: String) async throws
func register(data: RegistrationData) async throws
func getClientDetail(id: Int) async throws -> Client
func getClientNotes(clientId: Int) async throws -> [Note]
func addClientNote(clientId: Int, note: String) async throws
func updateLead(id: Int, data: LeadData) async throws -> Lead
func addLeadInteraction(leadId: Int, data: InteractionData) async throws

// Phase 2
func getOrders() async throws -> PaginatedResponse<Order>
func getOrderDetail(id: Int) async throws -> Order
func confirmOrder(id: Int) async throws
func cancelOrder(id: Int) async throws
func getMealEvents() async throws -> PaginatedResponse<MealEvent>
func createMealEvent(data: MealEventData) async throws -> MealEvent
func getMeals() async throws -> PaginatedResponse<Meal>
func createMeal(data: MealData) async throws -> Meal
func getDishes() async throws -> PaginatedResponse<Dish>
func createDish(data: DishData) async throws -> Dish

// Phase 3
func getMealPlans(clientId: Int) async throws -> [MealPlan]
func getPrepPlans() async throws -> [PrepPlan]
func getShoppingList(prepPlanId: Int) async throws -> ShoppingList
func getNotifications() async throws -> [Notification]
func getConversations() async throws -> [Conversation]
func sendMessage(conversationId: Int, content: String) async throws

// Phase 4
func getChefProfile() async throws -> ChefProfile
func updateChefProfile(data: ChefProfileData) async throws
func uploadPhoto(image: UIImage) async throws -> Photo
func getServiceAreas() async throws -> [ServiceArea]

// Phase 5
func getStripeStatus() async throws -> StripeStatus
func createStripeAccountLink() async throws -> URL
func getPaymentLinks() async throws -> [PaymentLink]
func createPaymentLink(data: PaymentLinkData) async throws -> PaymentLink
func getReceipts() async throws -> [Receipt]
```

---

## Milestones

| Milestone | Target | Features | Status |
|-----------|--------|----------|--------|
| **MVP** | Week 2 | Auth, Dashboard, Leads, Sous Chef | 🟡 In Progress |
| **Beta** | Week 6 | Orders, Meals, Events, Messaging | ⬜ Not Started |
| **1.0** | Week 10 | Full CRM, Meal Plans, Payments | ⬜ Not Started |
| **1.1** | Week 14 | Offline, Push, Analytics | ⬜ Not Started |

---

## Notes

- The Django backend has **~400 endpoints** - this is a significant undertaking
- Focus on chef-side features first (most valuable)
- Customer-side app could be separate or added later
- Consider React Native for faster cross-platform in future
- WebSocket support needed for real-time messaging
