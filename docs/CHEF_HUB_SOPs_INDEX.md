# Chef Hub - Standard Operating Procedures Index

## Overview

This document serves as the master index for all Chef Hub Standard Operating Procedures (SOPs). These procedures document every feature available in the Chef Hub dashboard, providing step-by-step guidance for chefs using the sautai platform.

![Chef Hub Dashboard](./screenshots/chef-hub-dashboard.png)
*The Chef Hub dashboard with sidebar navigation*

---

## Quick Navigation

| SOP | Description | File |
|-----|-------------|------|
| 📊 [Dashboard Overview](#dashboard-overview) | Main dashboard and navigation | *Below* |
| 👥 [Client Management](./CHEF_CLIENT_MANAGEMENT_SOP.md) | Managing clients and households | `CHEF_CLIENT_MANAGEMENT_SOP.md` |
| 💳 [Payment Links](./CHEF_PAYMENT_LINKS_SOP.md) | Creating and sending payment requests | `CHEF_PAYMENT_LINKS_SOP.md` |
| 🔗 [Connections](./CHEF_CONNECTIONS_SOP.md) | Managing customer connections | `CHEF_CONNECTIONS_SOP.md` |
| 💼 [Services & Pricing](./CHEF_SERVICES_PRICING_SOP.md) | Service offerings and pricing tiers | `CHEF_SERVICES_PRICING_SOP.md` |
| 🍽️ [Meals & Events](./CHEF_MEALS_EVENTS_SOP.md) | Creating meals and scheduling events | `CHEF_MEALS_EVENTS_SOP.md` |
| 👤 [Profile & Gallery](./CHEF_PROFILE_GALLERY_SOP.md) | Managing profile and photos | `CHEF_PROFILE_GALLERY_SOP.md` |
| 🍳 [Kitchen](./CHEF_KITCHEN_SOP.md) | Ingredients and dishes management | `CHEF_KITCHEN_SOP.md` |
| 📋 [Prep Planning](./CHEF_PREP_PLANNING_SOP.md) | Shopping lists and prep optimization | `CHEF_PREP_PLANNING_SOP.md` |

---

## Dashboard Overview

### Accessing Chef Hub
1. Log in to Hood United
2. Ensure you have a Chef account
3. Navigate to Chef Hub (automatic redirect for chef role)

### Dashboard Navigation

The Chef Hub sidebar contains the following sections:

```
┌─────────────────────────────────────────┐
│           CHEF HUB                       │
├─────────────────────────────────────────┤
│  📊 Dashboard       - Overview & stats   │
│  📋 Prep Planning   - Shopping & prep    │
│  👤 Profile         - Your bio & info    │
│  📷 Photos          - Gallery management │
│  🍳 Kitchen         - Ingredients/Dishes │
│  🔗 Connections     - Customer requests  │
│  👥 Clients         - Client management  │
│  💳 Payment Links   - Payment requests   │
│  💼 Services        - Service offerings  │
│  📅 Events          - Meal events        │
│  📦 Orders          - Order management   │
│  🍽️ Meals           - Meal creation      │
└─────────────────────────────────────────┘
```

### Dashboard Home

The main dashboard shows:
- **Stripe Connect Status** - Payment setup progress
- **Quick Stats** - Key business metrics
- **Pending Actions** - Items needing attention
- **Recent Activity** - Latest orders and connections

---

## SOP Summaries

### 👥 Client Management
**Purpose**: Manage all your clients in one place

**Key Features**:
- Unified view of platform and manual clients
- Household member tracking
- Dietary preferences and allergies
- Meal plan integration

**When to Use**: Adding clients, viewing dietary info, creating meal plans

[📖 Full SOP →](./CHEF_CLIENT_MANAGEMENT_SOP.md)

---

### 💳 Payment Links
**Purpose**: Request and collect payments professionally

**Key Features**:
- One-click payment link creation
- Automated email delivery
- Status tracking
- Stripe integration

**When to Use**: Billing clients, tracking payments, sending invoices

[📖 Full SOP →](./CHEF_PAYMENT_LINKS_SOP.md)

---

### 🔗 Connections
**Purpose**: Manage customer relationship lifecycle

**Key Features**:
- Connection request management
- Accept/decline workflow
- Active connection tracking
- Professional relationship ending

**When to Use**: Accepting new customers, managing client relationships

[📖 Full SOP →](./CHEF_CONNECTIONS_SOP.md)

---

### 💼 Services & Pricing
**Purpose**: Define your service offerings with flexible pricing

**Key Features**:
- Service type definitions
- Tiered pricing by household size
- Recurring subscriptions
- Private offerings for specific clients

**When to Use**: Setting up services, creating pricing, managing bookings

[📖 Full SOP →](./CHEF_SERVICES_PRICING_SOP.md)

---

### 🍽️ Meals & Events
**Purpose**: Create meals and schedule cooking events

**Key Features**:
- Meal creation with dishes
- Event scheduling
- Capacity management
- Dynamic pricing
- Order tracking

**When to Use**: Creating menus, scheduling events, managing orders

[📖 Full SOP →](./CHEF_MEALS_EVENTS_SOP.md)

---

### 👤 Profile & Gallery
**Purpose**: Manage your public presence

**Key Features**:
- Profile editing (bio, photos)
- Photo gallery management
- Break mode for time off
- Stripe Connect setup

**When to Use**: Updating profile, adding photos, taking a break

[📖 Full SOP →](./CHEF_PROFILE_GALLERY_SOP.md)

---

### 🍳 Kitchen (Ingredients & Dishes)
**Purpose**: Manage culinary building blocks

**Key Features**:
- Ingredient management with nutrition
- Dish creation with ingredients
- Meal building foundation
- Nutritional tracking

**When to Use**: Adding ingredients, creating dishes, tracking nutrition

[📖 Full SOP →](./CHEF_KITCHEN_SOP.md)

---

### 📋 Prep Planning
**Purpose**: Optimize shopping and reduce food waste

**Key Features**:
- Multi-client ingredient aggregation
- Smart timing recommendations
- Shelf life awareness
- Batch cooking suggestions

**When to Use**: Planning shopping, weekly prep, optimizing workflow

[📖 Full SOP →](./CHEF_PREP_PLANNING_SOP.md)

---

## Getting Started Workflow

For new chefs, follow this recommended setup order:

### Phase 1: Foundation Setup
1. ✅ Complete **Profile** setup (bio, photos)
2. ✅ Set up **Stripe Connect** for payments
3. ✅ Upload photos to **Gallery**

### Phase 2: Kitchen Setup
4. ✅ Add common **Ingredients** to Kitchen
5. ✅ Create **Dishes** from ingredients
6. ✅ Build **Meals** from dishes

### Phase 3: Business Setup
7. ✅ Define **Service Offerings** with pricing tiers
8. ✅ Create first **Event** for a meal

### Phase 4: Client Operations
9. ✅ Accept **Connections** from customers
10. ✅ Add off-platform **Clients** manually
11. ✅ Create **Payment Links** for services
12. ✅ Use **Prep Planning** for efficient shopping

---

## Feature Interdependencies

Understanding how features connect:

```
                    ┌─────────────┐
                    │   PROFILE   │
                    │  & GALLERY  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌─────│ CONNECTIONS │─────┐
              │     └──────┬──────┘     │
              │            │            │
       ┌──────▼──────┐    ▼     ┌──────▼──────┐
       │   CLIENTS   │◄────────►│   SERVICES  │
       └──────┬──────┘          └──────┬──────┘
              │                        │
              │    ┌─────────────┐     │
              └───►│   PAYMENT   │◄────┘
                   │    LINKS    │
                   └─────────────┘
                   
       ┌─────────────────────────────────┐
       │                                 │
       │  ┌─────────┐     ┌─────────┐   │
       │  │ KITCHEN │────►│  MEALS  │   │
       │  └─────────┘     └────┬────┘   │
       │                       │        │
       │                 ┌─────▼─────┐  │
       │                 │  EVENTS   │  │
       │                 └─────┬─────┘  │
       │                       │        │
       │           ┌───────────▼───────┐│
       │           │   PREP PLANNING   ││
       │           └───────────────────┘│
       └─────────────────────────────────┘
```

**Key Dependencies**:
- Dishes require Ingredients
- Meals require Dishes
- Events require Meals
- Payment Links require Clients (and Stripe)
- Prep Planning aggregates from Meals/Events/Plans

---

## Sous Chef AI Integration

All SOP features integrate with the **Sous Chef** AI assistant. You can ask:

**Client Management**
- "Show me clients with nut allergies"
- "What are the Johnson family's dietary restrictions?"

**Prep Planning**
- "Generate a prep plan for next week"
- "What's on my shopping list?"

**Meals & Events**
- "What events do I have scheduled?"
- "Create a meal with salmon"

**General**
- "Help me with [feature name]"
- "How do I [action]?"

---

## Support & Resources

### Getting Help
- **Sous Chef**: Ask the AI assistant
- **This Documentation**: Reference SOPs
- **Support**: Contact Hood United support

### Reporting Issues
If you encounter problems:
1. Check the Troubleshooting section in the relevant SOP
2. Try refreshing the page
3. Contact support with:
   - What you were trying to do
   - What happened
   - Any error messages

### Feature Requests
Have ideas for improvements?
- Use the feedback feature in Chef Hub
- Contact support with suggestions

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial SOP suite release |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

## Document Maintenance

These SOPs are maintained by the sautai development team and updated with each major feature release. For the latest information, always refer to the documentation in the repository.

**Last Updated**: December 2025

---

*Thank you for being a sautai chef! These SOPs are designed to help you succeed. If you find areas for improvement, please let us know.*

