# Chef Client Management - Standard Operating Procedure

## Overview

The **Client Management** feature in Chef Hub provides a unified view of all your clients—both platform-connected customers and manually-added contacts. It allows chefs to track household information, dietary preferences, allergies, manage connection requests, and create personalized meal plans for each client.

> **Note**: Connection management (accepting/declining customer requests) is now integrated directly into the Clients tab. There is no longer a separate Connections tab.

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Key Features](#key-features)
3. [How It Works](#how-it-works)
4. [Step-by-Step Guide](#step-by-step-guide)
5. [Managing Connection Requests](#managing-connection-requests)
6. [Understanding the Interface](#understanding-the-interface)
7. [Managing Meal Plans](#managing-meal-plans)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Independent chefs often work with a mix of clients:
- Some discovered through the Hood United platform  
- Some referred by existing clients
- Some from offline networking

Without a centralized system:
- Client information is scattered across notes, texts, and emails
- Dietary requirements get forgotten or confused
- Household members with different needs are hard to track
- Creating personalized meal plans becomes time-consuming

### The Solution
Client Management provides a single source of truth for all client information:
- **Unified View** - See platform and manual contacts in one place
- **Household Tracking** - Track each family member's preferences
- **Dietary Profiles** - Never forget an allergy or preference
- **Meal Plan Integration** - Create AI-powered meal plans directly from client profiles

---

## Key Features

### 1. Unified Client View
| Client Type | Description | Badge |
|-------------|-------------|-------|
| **Platform** | Customers who connected through Hood United | 🟢 Platform |
| **Manual** | Contacts you added manually (referrals, off-platform) | 📋 Manual |

### 2. Household Management
Track every member of a client's household:
- Names and relationships (spouse, child, etc.)
- Individual ages
- Per-person dietary preferences
- Per-person allergies
- Special notes

### 3. Dietary Profile Tracking
Comprehensive dietary tracking including:
- **Dietary Preferences**: Vegetarian, Vegan, Pescatarian, Keto, Paleo, Halal, Kosher, Gluten-Free, Low Sodium, Mediterranean, Whole30, FODMAP
- **Allergies**: Peanuts, Tree Nuts, Dairy, Eggs, Shellfish, Fish, Soy, Wheat, Sesame

### 4. Quick Stats Dashboard
At-a-glance metrics:
- Total client count
- Platform vs. manual breakdown
- Most common dietary preferences
- Most common allergies

### 5. Integrated Meal Planning
Create personalized meal plans directly from client profiles with AI assistance.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT SOURCES                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Platform Connections          Manual Contacts             │
│   ├── Accepted requests         ├── Referrals               │
│   ├── Profile data synced       ├── Networking contacts     │
│   └── Dietary from profile      └── Off-platform clients    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  UNIFIED CLIENT VIEW                         │
│                                                             │
│   All Clients (15)                                          │
│   ├── 🟢 Platform (8)                                       │
│   └── 📋 Manual (7)                                         │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ Johnson Family               🟢 Platform  👥 4      │  │
│   │ sarah.j@email.com                                   │  │
│   │ 🥬 Vegetarian  ⚠️ Dairy                             │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ Mike Chen                    📋 Manual    👥 2      │  │
│   │ mike.c@email.com                                    │  │
│   │ 🥗 Keto  ⚠️ Peanuts                                 │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   CLIENT DETAIL VIEW                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Johnson Family                                            │
│   📧 sarah.j@email.com  📞 (555) 123-4567                  │
│                                                             │
│   DIETARY PREFERENCES           ALLERGIES                   │
│   ┌─────────────────┐          ┌──────────────────┐        │
│   │ Vegetarian      │          │ ⚠️ Dairy         │        │
│   │ Low Sodium      │          │ ⚠️ Tree Nuts     │        │
│   └─────────────────┘          └──────────────────┘        │
│                                                             │
│   HOUSEHOLD (4 members)                                     │
│   ├── Sarah (Primary)                                       │
│   ├── Tom (Spouse, 38y) - Vegetarian                       │
│   ├── Emma (Child, 12y) - ⚠️ Peanuts                       │
│   └── Jack (Child, 8y) - No restrictions                   │
│                                                             │
│   [✨ Manage Meal Plans]                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Guide

### Step 1: Access Client Management
1. Log in to Chef Hub
2. Click **"Clients"** in the left sidebar navigation
3. You'll see your unified client list

### Step 2: Add a New Client

#### Adding a Manual Contact
1. Click the **"+ Add Client"** button in the top right
2. Fill in the required information:
   - **First Name** (required)
   - **Last Name** (optional)
   - **Email** (optional)
   - **Phone** (optional)
3. Select **Dietary Preferences** by clicking the relevant chips
4. Select **Allergies** by clicking the relevant chips
5. Add any **Notes** (e.g., "Met at farmers market, interested in weekly prep")
6. Click **"Save Client"**

> **Note**: Platform clients are added automatically when a customer connection is accepted.

### Step 3: View Client Details

1. Click on any client card in the list
2. The detail panel shows:
   - Contact information
   - Dietary preferences
   - Allergies
   - Household members
   - Notes
   - Meal plan access

### Step 4: Manage Household Members

#### Add a Household Member
1. Select a client from the list
2. In the Household section, click **"+ Add"**
3. Fill in member details:
   - **Name** (required)
   - **Relationship** (Spouse, Child, Parent, etc.)
   - **Age**
   - **Dietary Preferences**
   - **Allergies**
   - **Notes**
4. Click **"Add Member"**

#### Edit a Household Member
1. Click the **✏️** icon next to the member's name
2. Update the information
3. Click **"Update Member"**

#### Remove a Household Member
1. Click the **🗑️** icon next to the member's name
2. Confirm the removal

### Step 5: Edit Client Information

> **Note**: Only manual contacts can be edited. Platform clients' core info is synced from their profile.

1. Select a manual contact
2. Click **"✏️ Edit"** button
3. Update the information
4. Click **"Save Changes"**

### Step 6: Filter and Search Clients

#### Filter by Source
Click the stat cards at the top:
- **All Clients** - Show everyone
- **Platform** - Show only platform-connected clients
- **Manual** - Show only manually-added contacts

#### Search
Type in the search box to find clients by name or email.

#### Sort Options
Use the dropdown to sort by:
- Newest first
- Oldest first
- A → Z
- Z → A

### Step 7: Access Meal Plans

1. Select a client
2. Click **"✨ Manage Plans"** button in their profile
3. The Meal Plan Slideout opens (see Meal Planning SOP for details)

---

## Managing Connection Requests

Connection management is integrated directly into the Clients tab. Platform clients show their connection status and you can take action right from the client detail panel.

### Connection Lifecycle

```
Customer Request → Pending → Accepted (or Declined)
                              ↓
                        Active Client → End Connection (optional)
```

### Viewing Pending Requests

1. Go to the **Clients** tab
2. Look for the **orange badge** in the sidebar showing pending count
3. Client cards with pending status show an **⏳ Pending** badge
4. Click on a pending client to view their details

### Accepting a Connection

1. Select the client with a pending request
2. In the **Connection Status** section (shown in detail panel):
   - Click **"✓ Accept"** to approve the connection
3. The client becomes an active platform client
4. They gain access to your services

### Declining a Connection

1. Select the client with a pending request
2. In the Connection Status section:
   - Click **"Decline"** to reject the request
3. The customer is notified
4. They cannot immediately re-request

### Ending a Connection

1. Select an active platform client
2. In the Connection Status section:
   - Click **"End Connection"**
3. Confirm the action
4. **What happens:**
   - Customer loses access to book services
   - Existing orders are not affected
   - You can no longer create meal plans for them
   - History is preserved
   - Either party can reconnect later

### Connection Status Indicators

| Status | Indicator | Location |
|--------|-----------|----------|
| **Pending** | ⏳ Pending badge (orange) | Client card + detail panel |
| **Connected** | ✓ Connected badge (green) | Detail panel |
| **Badge Count** | Orange number badge | Sidebar "Clients" nav item |

---

## Understanding the Interface

### Client Card Elements

| Element | Description |
|---------|-------------|
| **Name** | Client's full name |
| **Badge** | 🟢 Platform or 📋 Manual |
| **Household Icon** | 👥 + number shows household size |
| **⚠️ Warning** | Yellow warning if household members are incomplete |
| **Email** | Contact email address |
| **Preference Chips** | Green chips showing dietary preferences |
| **Allergy Chips** | Red/yellow chips showing allergies |

### At a Glance Section

Shows aggregate data across all clients:
- **Dietary Breakdown**: Most common preferences with counts
- **Allergy Breakdown**: Most common allergies with counts

This helps you:
- Stock common ingredients
- Avoid common allergens
- Understand your client base

---

## Managing Meal Plans

### Creating a Meal Plan
1. Select a client
2. Click **"✨ Manage Plans"**
3. Click **"New Plan"** or start from a template
4. AI considers:
   - Client's dietary preferences
   - All household member allergies
   - Individual member preferences
   - Previous meal history

### AI-Powered Features
- **Full Week Generation**: AI creates 7 days of meals
- **Fill Empty Slots**: AI fills gaps in partial plans
- **Regenerate Single Day**: Replace meals for one day
- **Smart Suggestions**: Considers entire household

---

## Best Practices

### 1. Complete Household Profiles
When a client indicates multiple household members:
- Add each person individually
- Record their specific dietary needs
- Note ages for appropriate portion suggestions

### 2. Keep Notes Updated
Use the notes field to track:
- How you met the client
- Special occasions to remember
- Preferred service days
- Any feedback received

### 3. Verify Allergies
Always confirm allergies directly with clients—allergies shown in platform profiles may not be complete.

### 4. Regular Reviews
Periodically review client profiles:
- Update dietary preferences that may have changed
- Add new household members
- Archive clients who are no longer active

### 5. Use the "At a Glance" Data
Check aggregate dietary data before:
- Bulk ingredient purchases
- Creating new menu items
- Planning meal events

---

## Troubleshooting

### Can't edit a client's information

**Cause**: The client is a platform connection, not a manual contact.

**Solution**: Platform client core information (name, email) syncs from their profile. You can:
- Add/edit household members
- Add notes
- Create meal plans
- To update their info, ask them to update their profile

### Household size shows "claimed" vs actual

**Cause**: Customer indicated X household members during signup, but not all have been profiled.

**Solution**: Add individual profiles for each household member:
1. Click **"+ Add"** in the Household section
2. Add each person with their dietary info
3. The warning will clear when counts match

### Client not appearing in search

**Cause**: Search only matches name and email fields.

**Solution**:
1. Check spelling
2. Try searching by email
3. Clear any active filters
4. Check if client was accidentally deleted

### Changes not saving

**Cause**: Network issue or session timeout.

**Solution**:
1. Check your internet connection
2. Refresh the page
3. Log out and back in
4. Try again

---

## Technical Details

### Data Models

```python
# Platform clients come from
ChefCustomerConnection (status='accepted')
└── Customer profile data

# Manual clients stored as
Lead (status='won')
├── Contact information
├── Dietary preferences (JSON array)
├── Allergies (JSON array)
└── HouseholdMember (related)
    ├── Name, relationship, age
    ├── Dietary preferences
    └── Allergies
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chefs/api/me/all-clients/` | GET | List all unified clients |
| `/chefs/api/me/all-clients/<id>/` | GET | Get client detail |
| `/chefs/api/leads/` | POST | Create manual contact |
| `/chefs/api/leads/<id>/` | PATCH | Update manual contact |
| `/chefs/api/leads/<id>/` | DELETE | Delete manual contact |
| `/chefs/api/leads/<id>/household/` | POST | Add household member |
| `/chefs/api/leads/<id>/household/<member_id>/` | PATCH | Update member |
| `/chefs/api/leads/<id>/household/<member_id>/` | DELETE | Delete member |

### Dietary Options Available

```javascript
DIETARY_OPTIONS = [
  'Vegetarian', 'Vegan', 'Pescatarian', 'Keto', 'Paleo',
  'Halal', 'Kosher', 'Gluten-Free', 'Low Sodium',
  'Mediterranean', 'Whole30', 'FODMAP'
]

ALLERGY_OPTIONS = [
  'None', 'Peanuts', 'Tree Nuts', 'Dairy', 'Eggs',
  'Shellfish', 'Fish', 'Soy', 'Wheat', 'Sesame'
]
```

### Sous Chef Integration

The Client Management data is accessible through the Sous Chef AI assistant:

- "Show me my clients"
- "Who has peanut allergies?"
- "List vegetarian households"
- "Create a meal plan for the Johnson family"
- "What are the Smith family's dietary restrictions?"

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with unified client view |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*

