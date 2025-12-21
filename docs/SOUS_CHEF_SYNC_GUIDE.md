# Sous Chef Knowledge Sync Guide

## Overview

The **Sous Chef** is an AI assistant that helps chefs navigate the Chef Hub platform. When you make changes to the Chef Dashboard (add features, remove tabs, rename items, etc.), the Sous Chef must be updated to reflect those changes—otherwise it will give outdated or incorrect guidance to users.

This guide explains **what to update** and **how to update it** when making Chef Dashboard changes.

---

## Table of Contents

1. [Why This Matters](#why-this-matters)
2. [Quick Checklist](#quick-checklist)
3. [Files to Update](#files-to-update)
4. [Step-by-Step Process](#step-by-step-process)
5. [Examples](#examples)
6. [Testing Your Changes](#testing-your-changes)
7. [Common Scenarios](#common-scenarios)

---

## Why This Matters

The Sous Chef AI assistant:
- Guides chefs to specific dashboard tabs and features
- Explains how to use platform functionality
- Creates navigation actions (buttons that take users to specific tabs)
- Looks up SOP documentation when answering "how do I..." questions

If the Sous Chef's knowledge is outdated:
- ❌ Users get directed to tabs that don't exist
- ❌ Features are described incorrectly
- ❌ Documentation doesn't match the UI
- ❌ Users lose trust in the AI assistant

---

## Quick Checklist

When making Chef Dashboard changes, check these items:

- [ ] **System Prompt** - Update `meals/sous_chef_assistant.py` if features/tabs change
- [ ] **Topic Map** - Update `meals/sous_chef_tools.py` if help topics need redirecting
- [ ] **SOP Docs** - Update relevant file in `docs/CHEF_*_SOP.md`
- [ ] **Quick Actions** - Update `frontend/src/components/SousChefChat.jsx` if prompts need changing
- [ ] **Tests** - Update `frontend/tests/` if test assertions reference changed features

---

## Files to Update

### 1. System Prompt (`meals/sous_chef_assistant.py`)

**Purpose**: Defines what the Sous Chef knows about the platform.

**Key Section**: `ChefHubReference` table (around line 186-204)

```python
<!-- 5-F. CHEF HUB PLATFORM KNOWLEDGE -->
<ChefHubReference>
  You can help {chef_name} navigate Chef Hub features:
  
  | Feature | Purpose | Sidebar Location |
  |---------|---------|------------------|
  | Profile | Bio, photos, service areas, Calendly | Profile |
  | Photos | Upload gallery images | Photos |
  | Kitchen | Manage ingredients, dishes, meals | Kitchen |
  | Services | Create tiered pricing offerings | Services |
  | Events | Schedule meal events | Events |
  | Clients | Manage customers, households, and connection requests | Clients |
  | Payment Links | Send Stripe payment requests | Payment Links |
  | Prep Planning | Generate shopping lists | Prep Planning |
  | Break Mode | Temporarily pause operations | Dashboard toggle |
</ChefHubReference>
```

**When to update**: 
- Adding a new tab/feature
- Removing a tab/feature
- Renaming a tab/feature
- Changing what a feature does

---

### 2. SOP Topic Map (`meals/sous_chef_tools.py`)

**Purpose**: Maps user questions to documentation files.

**Key Section**: `SOP_TOPIC_MAP` dictionary (around line 483-505)

```python
SOP_TOPIC_MAP = {
    "profile": "CHEF_PROFILE_GALLERY_SOP.md",
    "gallery": "CHEF_PROFILE_GALLERY_SOP.md",
    "photos": "CHEF_PROFILE_GALLERY_SOP.md",
    "kitchen": "CHEF_KITCHEN_SOP.md",
    "ingredients": "CHEF_KITCHEN_SOP.md",
    "dishes": "CHEF_KITCHEN_SOP.md",
    "services": "CHEF_SERVICES_PRICING_SOP.md",
    "clients": "CHEF_CLIENT_MANAGEMENT_SOP.md",
    "connections": "CHEF_CLIENT_MANAGEMENT_SOP.md",  # Redirected after merge
    # ... etc
}
```

**When to update**:
- Adding new help topics
- Removing deprecated topics
- Redirecting topics to different docs (like when merging features)
- Creating new SOP documentation files

Also update the fallback message (around line 590):
```python
"Available topics: profile, gallery, photos, kitchen, services, events, meals, clients..."
```

---

### 3. SOP Documentation (`docs/CHEF_*_SOP.md`)

**Purpose**: Detailed step-by-step guides the Sous Chef can reference.

**Files**:
| File | Covers |
|------|--------|
| `CHEF_PROFILE_GALLERY_SOP.md` | Profile, gallery, photos, break mode, Stripe |
| `CHEF_KITCHEN_SOP.md` | Kitchen, ingredients, dishes |
| `CHEF_SERVICES_PRICING_SOP.md` | Services, pricing tiers |
| `CHEF_MEALS_EVENTS_SOP.md` | Meals, events |
| `CHEF_CLIENT_MANAGEMENT_SOP.md` | Clients, households, connections |
| `CHEF_PAYMENT_LINKS_SOP.md` | Payment links, invoicing |
| `CHEF_PREP_PLANNING_SOP.md` | Prep planning, shopping lists |

**When to update**:
- UI steps change
- New buttons/features added
- Workflows change
- Screenshots become outdated

---

### 4. Quick Actions (`frontend/src/components/SousChefChat.jsx`)

**Purpose**: Pre-defined prompts shown to users in the chat.

**Key Section**: `quickActions` array (around line 278-288)

```javascript
const quickActions = isGeneralMode ? [
  { label: '📚 Platform help', prompt: 'How do I use Chef Hub?' },
  { label: '💳 Payment links', prompt: 'How do I send a payment link to a client?' },
  { label: '🍳 Kitchen setup', prompt: 'How do I set up my kitchen with ingredients and dishes?' },
  { label: '📅 Scheduling', prompt: 'How do I manage events and meal schedules?' }
] : [
  // Family-specific prompts...
]
```

**When to update**:
- Adding major new features users should know about
- Removing deprecated features
- Changing how key workflows are accessed

---

### 5. Navigation Tool (`meals/sous_chef_tools.py`)

**Purpose**: Enables Sous Chef to create "Go to X" buttons.

**Key Section**: `DASHBOARD_TABS` constant and `navigate_to_dashboard_tab` function

The Sous Chef can generate navigation actions. If tab names change, ensure:
- The tab value matches what `ChefDashboard.jsx` expects
- The description matches the actual feature

---

## Step-by-Step Process

### When Adding a New Feature/Tab

1. **Update System Prompt**
   ```python
   # In meals/sous_chef_assistant.py, add to ChefHubReference table:
   | NewFeature | Description of what it does | NewFeature |
   ```

2. **Add SOP Topic Mapping**
   ```python
   # In meals/sous_chef_tools.py, add to SOP_TOPIC_MAP:
   "newfeature": "CHEF_NEW_FEATURE_SOP.md",
   "related_keyword": "CHEF_NEW_FEATURE_SOP.md",
   ```

3. **Create SOP Documentation**
   - Create `docs/CHEF_NEW_FEATURE_SOP.md`
   - Follow the format of existing SOPs
   - Include: Overview, Step-by-Step Guide, Troubleshooting

4. **Update Available Topics List**
   ```python
   # In meals/sous_chef_tools.py, update the fallback message:
   "Available topics: ..., newfeature, ..."
   ```

5. **Consider Quick Actions**
   - If it's a major feature, add a quick action prompt

---

### When Removing a Feature/Tab

1. **Update System Prompt**
   - Remove from `ChefHubReference` table

2. **Redirect Topic Mapping**
   ```python
   # Don't delete - redirect to the replacement feature:
   "oldfeature": "CHEF_REPLACEMENT_SOP.md",  # Redirected
   ```

3. **Update SOP Documentation**
   - Add deprecation notice to old SOP
   - Update the replacement SOP to include migrated functionality

4. **Update Available Topics List**
   - Remove or update the topic name

5. **Check Quick Actions**
   - Remove any prompts that reference the old feature

---

### When Renaming a Feature/Tab

1. **Update System Prompt**
   - Change the name in `ChefHubReference` table

2. **Add Topic Alias**
   ```python
   # Keep old name as alias, add new name:
   "oldname": "CHEF_FEATURE_SOP.md",  # Legacy alias
   "newname": "CHEF_FEATURE_SOP.md",
   ```

3. **Update SOP Documentation**
   - Update all references to the new name
   - Consider noting the rename for users

---

## Examples

### Example 1: Removing the Connections Tab

**Scenario**: Connection management was merged into the Clients tab.

**Changes Made**:

1. `meals/sous_chef_assistant.py`:
   ```diff
   - | Clients | Manage customers and households | Clients |
   - | Connections | Accept/decline customer requests | Connections |
   + | Clients | Manage customers, households, and connection requests (accept/decline/end) | Clients |
   ```

2. `meals/sous_chef_tools.py`:
   ```diff
   - "connections": "CHEF_CONNECTIONS_SOP.md",
   + "connections": "CHEF_CLIENT_MANAGEMENT_SOP.md",  # Redirected after merge
   + "accept": "CHEF_CLIENT_MANAGEMENT_SOP.md",
   + "decline": "CHEF_CLIENT_MANAGEMENT_SOP.md",
   ```

3. `docs/CHEF_CONNECTIONS_SOP.md`:
   ```markdown
   > ⚠️ **DEPRECATED**: The separate Connections tab has been merged into the **Clients** tab.
   > Please see CHEF_CLIENT_MANAGEMENT_SOP.md for current documentation.
   ```

4. `docs/CHEF_CLIENT_MANAGEMENT_SOP.md`:
   - Added "Managing Connection Requests" section

---

### Example 2: Adding a New "Analytics" Tab

**Hypothetical changes**:

1. `meals/sous_chef_assistant.py`:
   ```diff
   + | Analytics | View client metrics and business insights | Analytics |
   ```

2. `meals/sous_chef_tools.py`:
   ```python
   "analytics": "CHEF_ANALYTICS_SOP.md",
   "metrics": "CHEF_ANALYTICS_SOP.md",
   "insights": "CHEF_ANALYTICS_SOP.md",
   ```

3. Create `docs/CHEF_ANALYTICS_SOP.md` with full documentation

4. Update available topics message

5. Optionally add quick action:
   ```javascript
   { label: '📊 Analytics', prompt: 'How do I view my business analytics?' }
   ```

---

## Testing Your Changes

### Manual Testing

1. **Ask the Sous Chef about the feature**:
   - "How do I use [feature name]?"
   - "Where can I find [feature name]?"
   - "Take me to [feature name]"

2. **Verify responses are accurate**:
   - Tab names match the actual UI
   - Steps described match the actual workflow
   - No references to removed features

3. **Test navigation actions**:
   - If the Sous Chef offers a "Go to X" button, click it
   - Verify it takes you to the correct tab

### Automated Testing

Run the test suite:
```bash
cd frontend
npm test
```

Check `frontend/tests/chefDashboardConnections.test.mjs` and similar files for assertions that may need updating.

---

## Common Scenarios

| Scenario | What to Update |
|----------|----------------|
| **Tab renamed** | System prompt, SOP topic map (add alias), SOP docs |
| **Tab removed** | System prompt, SOP topic map (redirect), SOP docs (deprecate), tests |
| **Tab added** | System prompt, SOP topic map, create new SOP doc, update topics list |
| **Feature moved to different tab** | All of the above |
| **Button/workflow changed** | SOP docs only (unless major) |
| **New help topic needed** | SOP topic map, SOP docs |

---

## File Reference Summary

| File | Location | Purpose |
|------|----------|---------|
| System Prompt | `meals/sous_chef_assistant.py` | AI's knowledge of features |
| Topic Map | `meals/sous_chef_tools.py` | Maps questions → docs |
| SOP Docs | `docs/CHEF_*_SOP.md` | Detailed how-to guides |
| Quick Actions | `frontend/src/components/SousChefChat.jsx` | Pre-defined prompts |
| SOP Index | `docs/CHEF_HUB_SOPs_INDEX.md` | Index of all SOPs |
| Tests | `frontend/tests/*.test.mjs` | Automated assertions |

---

## Maintenance Notes

- **Review quarterly**: Check that all SOPs match current UI
- **After major releases**: Audit all Sous Chef knowledge files
- **Screenshots**: Keep SOP screenshots current (stored in `docs/screenshots/`)

---

*Last updated: December 2025*
*Maintainer: sautai development team*

