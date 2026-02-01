# Developer Directive: Sous Chef Workspace UI

## Overview

Build a settings interface that allows chefs to personalize their Sous Chef AI assistant. This follows the "OpenClaw pattern" where personality, rules, and memory are configurable per-user.

**Goal:** Let chefs customize how their AI assistant thinks, speaks, and remembers — without touching code.

---

## Data Models (Already Created)

```python
# chefs/models/sous_chef_memory.py

class ChefWorkspace(models.Model):
    chef = OneToOneField(Chef)
    soul_prompt = TextField()           # Personality/tone
    business_rules = TextField()        # Operating constraints
    enabled_tools = JSONField()         # Which tools are active
    tool_preferences = JSONField()      # Per-tool config
    include_analytics = BooleanField()  # Show stats in context
    include_seasonal = BooleanField()   # Show seasonal ingredients
    auto_memory_save = BooleanField()   # Auto-extract insights

class ClientContext(models.Model):
    chef = ForeignKey(Chef)
    client = ForeignKey(User, null=True)
    lead = ForeignKey(Lead, null=True)
    nickname = CharField()
    summary = TextField()
    cuisine_preferences = JSONField()   # ["Italian", "Japanese"]
    flavor_profile = JSONField()        # {"spicy": "mild", "sweet": "high"}
    cooking_notes = TextField()
    communication_style = CharField()
    special_occasions = JSONField()     # [{"name": "Birthday", "date": "2026-03-15"}]

# customer_dashboard/models.py (existing)
class ChefMemory(models.Model):
    chef = ForeignKey(Chef)
    memory_type = CharField()           # pattern, preference, lesson, todo
    content = TextField()
    importance = IntegerField(1-5)
    customer = ForeignKey(User, null=True)
    lead = ForeignKey(Lead, null=True)
    embedding = VectorField(1536)       # For semantic search
```

---

## UI Components to Build

### 1. Workspace Settings Panel

**Location:** Chef Hub → Settings → "Sous Chef" tab (or dedicated page)

**Sections:**

#### A. Personality (soul_prompt)
```
┌─────────────────────────────────────────────────────────────┐
│ 🎭 Sous Chef Personality                                    │
├─────────────────────────────────────────────────────────────┤
│ How should your Sous Chef communicate?                      │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Be warm and friendly, like a trusted kitchen partner.  │ │
│ │ Use casual language - no corporate speak.              │ │
│ │ Get excited about creative food ideas.                 │ │
│ │ Remember client preferences and mention them naturally.│ │
│ │ Be direct and concise.                                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ 💡 Tip: This shapes how Sous Chef talks to you.            │
│                                          [Save Changes]     │
└─────────────────────────────────────────────────────────────┘
```

**Field:** `<textarea>` for `soul_prompt`
**Placeholder:** Default soul prompt from `ChefWorkspace.get_default_soul_prompt()`
**Validation:** Max 2000 characters

#### B. Business Rules (business_rules)
```
┌─────────────────────────────────────────────────────────────┐
│ 📋 Business Rules & Constraints                             │
├─────────────────────────────────────────────────────────────┤
│ What rules should Sous Chef know about your business?       │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ - Minimum order: $75 for delivery, $50 for pickup      │ │
│ │ - Need 48 hours notice for orders over 5 people        │ │
│ │ - Don't take orders on Mondays (rest day)              │ │
│ │ - Specialize in comfort food with healthy twists       │ │
│ │ - Allergies are taken very seriously - always confirm  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ 💡 Sous Chef will reference these when making suggestions.  │
│                                          [Save Changes]     │
└─────────────────────────────────────────────────────────────┘
```

**Field:** `<textarea>` for `business_rules`
**Validation:** Max 2000 characters

#### C. Features Toggle
```
┌─────────────────────────────────────────────────────────────┐
│ ⚙️ Features                                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ [✓] Include business analytics in conversations            │
│     Sous Chef will reference your revenue, popular dishes  │
│                                                             │
│ [✓] Include seasonal ingredient suggestions                │
│     Get ideas based on what's in season                    │
│                                                             │
│ [✓] Auto-save insights from conversations                  │
│     Sous Chef will remember important things automatically │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Fields:** Checkboxes for `include_analytics`, `include_seasonal`, `auto_memory_save`

---

### 2. Memory Management Panel

**Location:** Chef Hub → Sous Chef → "Memory" tab

#### A. Memory List View
```
┌─────────────────────────────────────────────────────────────┐
│ 🧠 Sous Chef Memory                           [+ Add Note]  │
├─────────────────────────────────────────────────────────────┤
│ Filter: [All Types ▼] [All Clients ▼]        🔍 Search...   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ⭐⭐⭐⭐ [Lesson] Always check for nut allergies first      │
│ For: General • Created: Jan 15, 2026 • Accessed: 5 times   │
│                                               [Edit] [🗑️]   │
│ ─────────────────────────────────────────────────────────── │
│ ⭐⭐⭐ [Preference] The Smiths love extra garlic            │
│ For: Sarah Smith • Created: Jan 20, 2026 • Accessed: 3x    │
│                                               [Edit] [🗑️]   │
│ ─────────────────────────────────────────────────────────── │
│ ⭐⭐⭐ [Pattern] Batch cook rice on Sundays                 │
│ For: General • Created: Jan 22, 2026                       │
│                                               [Edit] [🗑️]   │
│ ─────────────────────────────────────────────────────────── │
│ ⭐⭐ [Todo] Research gluten-free pasta options              │
│ For: Chen Family • Created: Jan 25, 2026      [✓ Complete] │
│                                               [Edit] [🗑️]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Filter by `memory_type` (lesson, preference, pattern, todo)
- Filter by client/lead (or "General")
- Search (uses hybrid search - vector + text)
- Sort by importance, date, access count
- Edit inline or in modal
- Mark todos complete (sets `is_active=False`)
- Delete (soft delete via `is_active=False`)

#### B. Add/Edit Memory Modal
```
┌─────────────────────────────────────────────────────────────┐
│ ✏️ Add Memory                                          [X]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Type: [Lesson ▼]                                           │
│                                                             │
│ Content:                                                    │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Always double-check shellfish allergies with new       │ │
│ │ clients - some don't realize shrimp paste is in...     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Importance: ⭐⭐⭐☆☆ (3/5)                                  │
│                                                             │
│ Applies to: (○) General  (●) Specific Client               │
│             [Select Client ▼]                               │
│                                                             │
│                              [Cancel]  [Save Memory]        │
└─────────────────────────────────────────────────────────────┘
```

**Fields:**
- `memory_type`: Dropdown (lesson, preference, pattern, todo)
- `content`: Textarea (max 1000 chars)
- `importance`: Star rating 1-5
- `customer` or `lead`: Optional client selector

**On Save:** Call API that generates embedding automatically

---

### 3. Client Context Panel

**Location:** Chef Hub → Clients → [Client Detail] → "Preferences" tab

OR

**Location:** Sous Chef chat → When discussing a client → "Edit Preferences" button

```
┌─────────────────────────────────────────────────────────────┐
│ 👤 Sarah Smith - Preferences                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Nickname: [ The Smiths ]                                    │
│                                                             │
│ Quick Summary:                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Family of 4, adventurous eaters. Dad has nut allergy.  │ │
│ │ Kids love pasta. Weekly meal prep on Sundays.          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Cuisine Preferences:                                        │
│ [Italian] [Japanese] [Mexican] [+ Add]                      │
│                                                             │
│ Flavor Profile:                                             │
│   Spicy:    [░░░░░████░] Medium-High                       │
│   Sweet:    [░░░░░░░░░░] Low                               │
│   Savory:   [██████████] High                              │
│   Sour:     [░░░░░░░░░░] Low                               │
│                                                             │
│ Cooking Notes:                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Prefer al dente pasta. Extra garlic always welcome.    │ │
│ │ Kids like mild sauces on the side.                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Special Occasions:                                          │
│ 🎂 Sarah's Birthday - March 15                    [Remove]  │
│ 💍 Anniversary - June 20                          [Remove]  │
│                                    [+ Add Occasion]         │
│                                                             │
│                                          [Save Preferences] │
└─────────────────────────────────────────────────────────────┘
```

**Fields:**
- `nickname`: Text input
- `summary`: Textarea
- `cuisine_preferences`: Tag input (add/remove)
- `flavor_profile`: Sliders or segmented controls
- `cooking_notes`: Textarea
- `special_occasions`: List with date picker

---

## API Endpoints to Create

### Workspace API
```
GET    /api/chef/workspace/           → Get current chef's workspace
PUT    /api/chef/workspace/           → Update workspace settings
POST   /api/chef/workspace/reset/     → Reset to defaults
```

### Memory API
```
GET    /api/chef/memories/            → List memories (with filters)
POST   /api/chef/memories/            → Create memory (auto-generates embedding)
GET    /api/chef/memories/{id}/       → Get single memory
PUT    /api/chef/memories/{id}/       → Update memory (regenerates embedding)
DELETE /api/chef/memories/{id}/       → Soft delete memory
POST   /api/chef/memories/search/     → Hybrid search (vector + text)
POST   /api/chef/memories/{id}/complete/  → Mark todo as complete
```

### Client Context API
```
GET    /api/chef/clients/{id}/context/    → Get client context
PUT    /api/chef/clients/{id}/context/    → Update client context
DELETE /api/chef/clients/{id}/context/    → Reset client context
```

---

## Frontend Components (React)

```
src/components/souschef/
├── WorkspaceSettings/
│   ├── PersonalityEditor.tsx      # soul_prompt textarea
│   ├── BusinessRulesEditor.tsx    # business_rules textarea
│   ├── FeatureToggles.tsx         # checkboxes
│   └── WorkspaceSettings.tsx      # container
├── MemoryManager/
│   ├── MemoryList.tsx             # filterable list
│   ├── MemoryCard.tsx             # single memory display
│   ├── MemoryEditor.tsx           # add/edit modal
│   ├── MemorySearch.tsx           # search input
│   └── MemoryManager.tsx          # container
├── ClientContext/
│   ├── PreferencesEditor.tsx      # full preferences form
│   ├── CuisineTagInput.tsx        # tag input for cuisines
│   ├── FlavorSliders.tsx          # flavor profile sliders
│   ├── OccasionsList.tsx          # special occasions
│   └── ClientContext.tsx          # container
└── index.ts
```

---

## Integration Points

### 1. Sous Chef Chat
When opening chat with a client selected:
- Load `ClientContext` and display summary badge
- "Edit Preferences" button opens ClientContext panel
- After conversation, offer to save insights as memories

### 2. Onboarding
For new chefs:
- Prompt to set personality on first Sous Chef use
- Wizard: "How should your assistant communicate?"
- Pre-written templates to choose from

### 3. Quick Actions
In Sous Chef chat, add buttons:
- "💾 Save as Memory" → Opens MemoryEditor with content pre-filled
- "✏️ Edit Client Preferences" → Opens ClientContext for current client

---

## Implementation Priority

1. **Phase 1 (MVP):** WorkspaceSettings page with soul_prompt + business_rules
2. **Phase 2:** Memory list view with basic CRUD
3. **Phase 3:** Client context editor
4. **Phase 4:** Memory search with hybrid (vector + text)
5. **Phase 5:** Auto-save insights, onboarding wizard

---

## Serializers (Django REST Framework)

```python
# chefs/serializers.py

class ChefWorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChefWorkspace
        fields = [
            'soul_prompt', 'business_rules', 'enabled_tools',
            'tool_preferences', 'include_analytics', 
            'include_seasonal', 'auto_memory_save'
        ]

class ChefMemorySerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ChefMemory
        fields = [
            'id', 'memory_type', 'content', 'importance',
            'customer', 'lead', 'client_name', 'created_at',
            'updated_at', 'access_count', 'is_active'
        ]
    
    def get_client_name(self, obj):
        if obj.customer:
            return obj.customer.get_full_name()
        if obj.lead:
            return f"{obj.lead.first_name} {obj.lead.last_name}"
        return None

class ClientContextSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ClientContext
        fields = [
            'id', 'nickname', 'summary', 'cuisine_preferences',
            'flavor_profile', 'cooking_notes', 'communication_style',
            'special_occasions', 'total_orders', 'total_spent_cents',
            'client_name'
        ]
```

---

## Notes

- All memory writes should trigger embedding generation (async via Celery if slow)
- Memory search should fall back to text-only if vector search fails
- Client context should auto-populate `total_orders` and `total_spent_cents` from order history
- Consider rate limiting on memory creation (prevent spam)
- Add character counters to textareas
