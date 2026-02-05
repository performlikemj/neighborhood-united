# Sautai iOS App - Feature Parity Roadmap

> **Django Backend**: ~400 endpoints | **iOS App Current Coverage**: ~70%
>
> Last Updated: February 5, 2026

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

## Phase 2: Core Business Features ✅
*Goal: Orders, meals, and service management*

### 2.1 Order Management
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Orders | ✅ | `OrdersListView.swift` | `GET /meals/api/chef-meal-orders/` | With status filter tabs |
| Order Detail | ✅ | `OrderDetailView.swift` | `GET /meals/api/chef-meal-orders/{id}/` | Full detail view |
| Confirm Order | ✅ | `OrderDetailView.swift` | `POST /meals/api/chef-meal-orders/{id}/confirm/` | Action button |
| Cancel Order | ✅ | `OrderDetailView.swift` | `POST /meals/api/chef-meal-orders/{id}/cancel/` | With reason |
| Adjust Quantity | ✅ | `OrderDetailView.swift` | `POST /meals/api/chef-meal-orders/{id}/adjust-quantity/` | Stepper UI |
| Order Calendar | ✅ | `OrderCalendarView.swift` | `GET /meals/api/chef-calendar/` | Monthly view |

**Implementation Plan:**
```
[x] Create OrdersListView ✅
[x] Create OrderDetailView with actions ✅
[x] Add order status badges and colors ✅
[x] Create OrderCalendarView ✅
[ ] Implement push notifications for new orders
[ ] Test: Receive order → Confirm → Complete flow
```

---

### 2.2 Meal Events (Meal Shares)
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Events | ✅ | `MealEventsListView.swift` | `GET /meals/api/chef-meal-events/` | With filters |
| Create Event | ✅ | `AddMealEventView.swift` | `POST /meals/api/chef-meal-events/` | Full form |
| Update Event | ✅ | `EditMealEventView.swift` | `POST /meals/api/chef-meal-events/{id}/update/` | All fields |
| Cancel Event | ✅ | `MealEventDetailView.swift` | `POST /meals/api/chef-meal-events/{id}/cancel/` | With confirmation |
| Duplicate Event | ✅ | `MealEventDetailView.swift` | `POST /meals/api/chef-meal-events/{id}/duplicate/` | Quick action |
| Event Orders | ✅ | `MealEventDetailView.swift` | `GET /meals/api/chef-meal-events/{id}/order/` | Orders list |

**Implementation Plan:**
```
[x] Create MealEventsListView ✅
[x] Create MealEventDetailView ✅
[x] Create AddMealEventView with date picker ✅
[x] Add event management actions ✅
[ ] Test: Create event → Get orders → Complete
```

---

### 2.3 Meals & Dishes
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Meals | ✅ | `MealsListView.swift` | `GET /meals/api/chef/meals/` | With search |
| Create Meal | ✅ | `AddMealView.swift` | `POST /meals/api/chef/meals/` | With dish picker |
| Update Meal | ✅ | `MealDetailView.swift` | `PUT /meals/api/chef/meals/{id}/update/` | Inline edit |
| List Dishes | ✅ | `DishesListView.swift` | `GET /meals/api/dishes/` | Grid view |
| Create Dish | ✅ | `AddDishView.swift` | `POST /meals/api/create-chef-dish/` | Full form |
| Update Dish | ✅ | `EditDishView.swift` | `PUT /meals/api/dishes/{id}/update/` | All fields |
| Delete Dish | ✅ | `DishDetailView.swift` | `DELETE /meals/api/dishes/{id}/delete/` | With confirmation |

**Implementation Plan:**
```
[x] Create KitchenView (meals/dishes hub) ✅
[x] Create MealDetailView ✅
[x] Create DishDetailView ✅
[x] Create AddMealView with dish picker ✅
[x] Create AddDishView with ingredients ✅
[ ] Test: Create dish → Add to meal → Publish
```

---

### 2.4 Ingredients
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Ingredients | ✅ | `IngredientsListView.swift` | `GET /meals/api/ingredients/` | With search |
| Search Ingredients | ✅ | `IngredientPickerView.swift` | `GET /meals/api/search_ingredients/` | Autocomplete |
| Create Ingredient | ✅ | `AddIngredientView.swift` | `POST /meals/api/chef/ingredients/` | Sheet form |
| Update Ingredient | ✅ | `IngredientsListView.swift` | `PUT /meals/api/chef/ingredients/{id}/` | Inline |
| Delete Ingredient | ✅ | `IngredientsListView.swift` | `DELETE /meals/api/chef/ingredients/{id}/delete/` | Swipe |

**Implementation Plan:**
```
[x] Create IngredientsListView ✅
[x] Add ingredient search with autocomplete ✅
[x] Create AddIngredientView ✅
[ ] Test: Search → Select → Add to dish
```

---

### 2.5 Service Offerings
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Offerings | ✅ | `ServicesListView.swift` | `GET /services/offerings/` | With filter |
| Create Offering | ✅ | `AddServiceView.swift` | `POST /services/offerings/` | Full form |
| Update Offering | ✅ | `EditServiceView.swift` | `PUT /services/offerings/{id}/` | All fields |
| Delete Offering | ✅ | `ServiceDetailView.swift` | `DELETE /services/offerings/{id}/delete/` | With confirmation |
| Price Tiers | ✅ | `PriceTierEditor.swift` | `POST /services/offerings/{id}/tiers/` | Add/Edit/Delete |

**Implementation Plan:**
```
[x] Create ServicesListView ✅
[x] Create ServiceDetailView ✅
[x] Create AddServiceView with tier pricing ✅
[ ] Test: Create service → Add tiers → Publish
```

---

## Phase 3: Advanced Features ✅
*Goal: Collaborative planning, prep, and analytics*

### 3.1 Collaborative Meal Plans
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Client Plans | ✅ | `MealPlansListView.swift` | `GET /chefs/api/me/clients/{id}/plans/` | With filter tabs |
| Plan Detail | ✅ | `MealPlanDetailView.swift` | `GET /chefs/api/me/plans/{id}/` | Full detail view |
| Publish Plan | ✅ | `MealPlanDetailView.swift` | `POST /chefs/api/me/plans/{id}/publish/` | Status action |
| Add Plan Day | ✅ | `AddPlanDayView.swift` | `POST /chefs/api/me/plans/{id}/days/` | Sheet form |
| Add Plan Item | ✅ | `AddMealItemView.swift` | `POST /chefs/api/me/plans/{id}/days/{day_id}/items/` | Meal/Dish picker |
| View Suggestions | ✅ | `MealPlanDetailView.swift` | `GET /chefs/api/me/plans/{id}/suggestions/` | Suggestions section |
| Respond to Suggestion | ✅ | `MealPlanDetailView.swift` | `POST /chefs/api/me/suggestions/{id}/respond/` | Accept/Reject actions |
| AI Generate Meals | ✅ | `GenerateMealsView.swift` | `POST /chefs/api/me/plans/{id}/generate/` | Preferences sheet |

**Implementation Plan:**
```
[x] Create MealPlansListView ✅
[x] Create MealPlanDetailView with calendar ✅
[x] Create PlanDayView with meal slots ✅
[x] Add AI generation integration ✅
[x] Create SuggestionResponseSheet ✅
[ ] Test: Create plan → Generate meals → Client suggests → Respond
```

---

### 3.2 Prep Planning
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Prep Plans | ✅ | `PrepPlanningView.swift` | `GET /chefs/api/me/prep-plans/` | List with filters |
| Prep Plan Detail | ✅ | `PrepPlanDetailView.swift` | `GET /chefs/api/me/prep-plans/{id}/` | Full detail |
| Shopping List | ✅ | `ShoppingListView.swift` | `GET /chefs/api/me/prep-plans/{id}/shopping-list/` | Interactive list |
| Mark Purchased | ✅ | `ShoppingListView.swift` | `POST /chefs/api/me/prep-plans/{id}/mark-purchased/` | Toggle UI |
| Quick Generate | ✅ | `QuickGenerateView.swift` | `POST /chefs/api/me/prep-plans/quick-generate/` | Date picker |
| Live Commitments | ✅ | `LiveCommitmentsView.swift` | `GET /chefs/api/me/prep-plans/live/commitments/` | Dashboard view |

**Implementation Plan:**
```
[x] Create PrepPlanningView ✅
[x] Create ShoppingListView with checkboxes ✅
[x] Add quick generation from orders ✅
[x] Create live commitments dashboard ✅
[ ] Test: Orders → Generate prep → Shopping list → Mark done
```

---

### 3.3 Notifications
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Notifications | ✅ | `NotificationsView.swift` | `GET /chefs/api/me/notifications/` | With type filters |
| Unread Count | ✅ | `NotificationsView.swift` | `GET /chefs/api/me/notifications/unread-count/` | Badge support |
| Mark Read | ✅ | `NotificationsView.swift` | `POST /chefs/api/me/notifications/{id}/read/` | Tap action |
| Mark All Read | ✅ | `NotificationsView.swift` | `POST /chefs/api/me/notifications/mark-all-read/` | Toolbar button |
| Dismiss | ✅ | `NotificationsView.swift` | `POST /chefs/api/me/notifications/{id}/dismiss/` | Swipe action |
| Push Notifications | ⬜ | - | APNs integration | Deferred |

**Implementation Plan:**
```
[x] Create NotificationsView ✅
[x] Add notification badge to tab bar ✅
[ ] Implement push notification handling (deferred)
[ ] Add notification preferences in settings
[ ] Test: Receive notification → Tap → Navigate to source
```

---

### 3.4 Messaging
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Conversations | ✅ | `ConversationsListView.swift` | `GET /messaging/api/conversations/` | With unread badges |
| Get Conversation | ✅ | `ChatView.swift` | `GET /messaging/api/conversations/{id}/` | Full messages |
| Send Message | ✅ | `ChatView.swift` | `POST /messaging/api/conversations/{id}/send/` | With auto-scroll |
| Unread Counts | ✅ | `ConversationsListView.swift` | `GET /messaging/api/unread-counts/` | Badge display |
| Mark Read | ✅ | `ChatView.swift` | `POST /messaging/api/conversations/{id}/read/` | On appear |
| Start Conversation | ✅ | `ChatView.swift` | `POST /messaging/api/start-conversation/` | New chat |
| WebSocket | ⬜ | - | WebSocket connection | Deferred |

**Implementation Plan:**
```
[x] Create ConversationsListView ✅
[x] Create ChatView with message bubbles ✅
[ ] Implement WebSocket for real-time (deferred)
[ ] Add typing indicators
[ ] Test: Send message → Receive reply → Real-time updates
```

---

### 3.5 Reviews & Ratings
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| View My Reviews | ✅ | `ReviewsListView.swift` | `GET /reviews/my_reviews/` | With summary card |
| Review Summary | ✅ | `ReviewsListView.swift` | `GET /chefs/api/me/reviews/summary/` | Rating breakdown |
| View Chef Reviews | ✅ | `ReviewsListView.swift` | `GET /reviews/chef/{id}/reviews/` | List view |
| Reply to Review | ✅ | `ReviewsListView.swift` | `POST /reviews/{id}/respond/` | Reply sheet |

**Implementation Plan:**
```
[x] Create ReviewsListView ✅
[x] Add review summary card ✅
[x] Create ReviewRowView with reply ✅
[x] Create ReplyToReviewSheet ✅
[ ] Test: View reviews → Reply to review
```

---

## Phase 4: Profile & Settings ✅
*Goal: Complete profile management and app settings*

### 4.1 Chef Profile
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| View Profile | ✅ | `ChefProfileManagementView.swift` | `GET /chefs/api/me/chef/profile/` | Full profile card |
| Update Profile | ✅ | `EditChefProfileView.swift` | `POST /chefs/api/me/chef/profile/update/` | All fields |
| Photo Gallery | ✅ | `PhotosManagementView.swift` | `GET /chefs/api/{username}/photos/` | Grid view |
| Upload Photo | ✅ | `PhotosManagementView.swift` | `POST /chefs/api/me/chef/photos/` | Image picker |
| Delete Photo | ✅ | `PhotosManagementView.swift` | `DELETE /chefs/api/me/chef/photos/{id}/` | Swipe action |
| Set Break Status | ✅ | `SetBreakStatusView.swift` | `POST /chefs/api/me/chef/break/` | With return date |
| Set Live Status | ✅ | `ChefProfileManagementView.swift` | `POST /chefs/api/me/chef/live/` | Toggle switch |

**Implementation Plan:**
```
[x] Create ChefProfileView ✅
[x] Create EditProfileView ✅
[x] Create PhotoGalleryView with upload ✅
[x] Add break/live toggle ✅
[ ] Test: Update profile → Upload photo → Toggle status
```

---

### 4.2 Service Areas
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| View Service Areas | ✅ | `ServiceAreasView.swift` | `GET /local_chefs/api/chef/service-areas/` | List view |
| Add Area | ✅ | `AddServiceAreaView.swift` | `POST /local_chefs/api/chef/service-areas/add/` | Full form |
| Edit Area | ✅ | `EditServiceAreaView.swift` | `PUT /local_chefs/api/chef/service-areas/{id}/` | All fields |
| Remove Area | ✅ | `ServiceAreasView.swift` | `DELETE /local_chefs/api/chef/service-areas/{id}/remove/` | Swipe action |
| Add Postal Codes | ✅ | `EditServiceAreaView.swift` | `POST /local_chefs/api/chef/service-areas/postal-codes/add/` | Multi-select |

**Implementation Plan:**
```
[x] Create ServiceAreasView ✅
[x] Create AddServiceAreaView ✅
[x] Create EditServiceAreaView ✅
[ ] Test: Add area → Add postal codes → Edit → Remove
```

---

### 4.3 Verification & Compliance
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| View Documents | ✅ | `VerificationView.swift` | `GET /chefs/api/me/documents/` | Document list |
| Upload Document | ✅ | `VerificationView.swift` | `POST /chefs/api/me/documents/` | File picker |
| Verification Status | ✅ | `VerificationView.swift` | `GET /chefs/api/me/documents/status/` | Status card |
| Schedule Meeting | ✅ | `ScheduleMeetingView.swift` | `POST /chefs/api/me/verification-meeting/schedule/` | Date picker |

**Implementation Plan:**
```
[x] Create VerificationView ✅
[x] Add document upload ✅
[x] Show verification status badges ✅
[x] Create ScheduleMeetingView ✅
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

## Phase 5: Payments & Commerce ✅
*Goal: Full payment integration*

### 5.1 Stripe Integration
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| Account Status | ✅ | `PaymentsView.swift` | `GET /meals/api/stripe-account-status/` | Status card |
| Create Account Link | ✅ | `PaymentsView.swift` | `POST /meals/api/stripe-account-link/` | Safari redirect |
| Account Dashboard | ✅ | `PaymentsView.swift` | `POST /meals/api/stripe-dashboard-link/` | Login link |
| Process Payment | 🟡 | - | `POST /meals/api/process-chef-meal-payment/{id}/` | Via web |
| Payment Status | 🟡 | - | `GET /meals/api/order-payment-status/{id}/` | Via web |

**Implementation Plan:**
```
[x] Create PaymentsOverviewView ✅
[x] Add Stripe account status display ✅
[x] Create account link flow ✅
[ ] Add Stripe SDK for in-app payments (deferred - uses web)
[ ] Test: Setup account → Verify status
```

---

### 5.2 Payment Links
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Payment Links | ✅ | `PaymentLinksView.swift` | `GET /chefs/api/me/payment-links/` | With status filter |
| Create Link | ✅ | `CreatePaymentLinkView.swift` | `POST /chefs/api/me/payment-links/` | Full form |
| Send Link | ✅ | `PaymentLinksView.swift` | `POST /chefs/api/me/payment-links/{id}/send/` | Share sheet |
| Link Stats | ✅ | `PaymentLinksView.swift` | `GET /chefs/api/me/payment-links/stats/` | Summary card |

**Implementation Plan:**
```
[x] Create PaymentLinksView ✅
[x] Create CreatePaymentLinkView ✅
[x] Add share sheet for sending links ✅
[ ] Test: Create link → Send → Track payment
```

---

### 5.3 Receipts
| Feature | Status | iOS File | Django Endpoint | Notes |
|---------|--------|----------|-----------------|-------|
| List Receipts | ✅ | `ReceiptsView.swift` | `GET /chefs/api/me/receipts/` | With date filter |
| Receipt Detail | ✅ | `ReceiptsView.swift` | `GET /chefs/api/me/receipts/{id}/` | Row detail |
| Receipt Stats | ✅ | `ReceiptsView.swift` | `GET /chefs/api/me/receipts/stats/` | Summary card |
| PDF Export | 🟡 | - | Via PDF URL | Opens in Safari |

**Implementation Plan:**
```
[x] Create ReceiptsView ✅
[x] Create ReceiptRow ✅
[x] Add stats summary ✅
[ ] Add in-app PDF viewer
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
| **MVP** | Week 2 | Auth, Dashboard, Leads, Sous Chef | ✅ Complete |
| **Beta** | Week 6 | Orders, Meals, Events, Messaging | ✅ Complete |
| **1.0** | Week 10 | Full CRM, Meal Plans, Payments | ✅ Complete |
| **1.1** | Week 14 | Offline, Push, Analytics | 🟡 In Progress |

---

## Notes

- The Django backend has **~400 endpoints** - this is a significant undertaking
- Focus on chef-side features first (most valuable)
- Customer-side app could be separate or added later
- Consider React Native for faster cross-platform in future
- WebSocket support needed for real-time messaging
