# Sensitive Data Handling Plan

## Problem Statement

The Sous Chef AI has access to customer health data (allergies, dietary restrictions) via tools like `get_family_dietary_summary`. While prompt guidance tells the model not to share this over Telegram, **the model ignores the guidance**.

Evidence: Screenshot shows bot returning "Client: Michael - Allergies: None listed" over Telegram.

## Design Principles

1. **Defense in depth** - Don't rely solely on LLM prompt compliance
2. **Channel-aware tools** - Tools enforce their own restrictions
3. **Fail-safe** - If unsure, don't expose data
4. **Helpful redirects** - Tell user where to find the data instead

## Solution: Sensitive Data Category + Tool Wrappers

### Approach

Create a new `SENSITIVE` tool category. When these tools are called from restricted channels (Telegram, LINE), return a redirect message instead of actual data.

```python
# Telegram request for allergies
Tool call: get_family_dietary_summary()

# Instead of returning actual data:
{
    "status": "restricted",
    "channel": "telegram",
    "message": "I can't share dietary/allergy details over Telegram for privacy. Please check the dashboard under Family → Dietary Info, or ask me when you're on the web app."
}
```

### Sensitive Tools Identified

| Tool | Sensitive Data | Action on Telegram |
|------|----------------|-------------------|
| `get_family_dietary_summary` | Allergies, dietary restrictions, member names | Redirect to dashboard |
| `get_household_members` | Names, ages, dietary info per member | Redirect to dashboard |
| `check_recipe_compliance` | References specific allergies in response | Return safe/unsafe only, no details |
| `suggest_ingredient_substitution` | References specific allergies | Generic suggestion only |

### Non-Sensitive Tools (OK on all channels)

- `get_family_order_history` - Order data, not health data
- `get_upcoming_family_orders` - Schedule only
- `add_family_note` - Writing, not reading sensitive data
- `suggest_family_menu` - Suggestions, no raw health data exposed
- All chef analytics, prep, scheduling tools

---

## Implementation Phases

### Phase 1: Define Sensitivity Categories

**Files:**
- `chefs/services/sous_chef/tools/categories.py`

**Changes:**
1. Add `SENSITIVE = "sensitive"` to `ToolCategory` enum
2. Add sensitive tools to registry with new category
3. Define `SENSITIVE_RESTRICTED_CHANNELS = {"telegram", "line"}`

**Tests first:**
```python
def test_sensitive_category_exists():
    assert ToolCategory.SENSITIVE == "sensitive"

def test_sensitive_tools_identified():
    assert TOOL_REGISTRY["get_family_dietary_summary"] == ToolCategory.SENSITIVE

def test_telegram_allows_sensitive_category():
    # Sensitive tools ARE loaded, but wrapped
    categories = get_categories_for_channel("telegram")
    assert ToolCategory.SENSITIVE in categories
```

### Phase 2: Sensitive Data Wrapper

**Files:**
- `chefs/services/sous_chef/tools/sensitive_wrapper.py` (new)

**Design:**
```python
class SensitiveDataWrapper:
    """Wraps sensitive tools to enforce channel restrictions."""
    
    REDIRECT_MESSAGES = {
        "get_family_dietary_summary": (
            "🔒 For privacy, I can't share dietary details over {channel}. "
            "Please check the dashboard: Family → Dietary Info"
        ),
        "get_household_members": (
            "🔒 Household member details aren't available over {channel}. "
            "View them on the dashboard: Family → Members"
        ),
    }
    
    def wrap_tool(self, tool_fn, tool_name: str, channel: str):
        """Return wrapped function that checks channel."""
        if channel not in SENSITIVE_RESTRICTED_CHANNELS:
            return tool_fn  # No wrapping needed
        
        def wrapped(*args, **kwargs):
            return {
                "status": "restricted",
                "channel": channel,
                "message": self.REDIRECT_MESSAGES.get(tool_name, 
                    f"This information isn't available over {channel}.")
            }
        return wrapped
```

**Tests first:**
```python
def test_wrapper_blocks_dietary_on_telegram():
    wrapper = SensitiveDataWrapper()
    wrapped = wrapper.wrap_tool(mock_dietary_fn, "get_family_dietary_summary", "telegram")
    result = wrapped()
    assert result["status"] == "restricted"
    assert "dashboard" in result["message"].lower()

def test_wrapper_allows_dietary_on_web():
    wrapper = SensitiveDataWrapper()
    wrapped = wrapper.wrap_tool(mock_dietary_fn, "get_family_dietary_summary", "web")
    result = wrapped()
    assert result["status"] == "success"  # Original function called
```

### Phase 3: Integrate with Tool Loader

**Files:**
- `chefs/services/sous_chef/tools/loader.py`

**Changes:**
1. Import `SensitiveDataWrapper`
2. When loading tools for a channel, wrap sensitive ones
3. Pass channel context through execution

**Tests first:**
```python
def test_loader_wraps_sensitive_tools_for_telegram():
    tools = get_tools_for_channel("telegram")
    # Find the dietary tool
    dietary_tool = next(t for t in tools if t["name"] == "get_family_dietary_summary")
    # Execute it
    result = execute_tool("get_family_dietary_summary", {}, channel="telegram")
    assert result["status"] == "restricted"

def test_loader_does_not_wrap_for_web():
    result = execute_tool("get_family_dietary_summary", {}, channel="web")
    assert result["status"] == "success"
```

### Phase 4: Partial Data for Some Tools

For `check_recipe_compliance`, we want to give a useful answer without exposing specifics:

**Current response:**
```json
{
    "is_compliant": false,
    "issues": ["⚠️ ALLERGEN ALERT: 'peanut butter' contains peanuts (Sarah is allergic)"]
}
```

**Telegram response:**
```json
{
    "is_compliant": false,
    "message": "⚠️ This recipe has compliance issues. Check the dashboard for details."
}
```

**Tests first:**
```python
def test_recipe_compliance_telegram_no_names():
    result = execute_tool("check_recipe_compliance", 
        {"ingredients": ["peanut butter"]}, 
        channel="telegram"
    )
    assert result["is_compliant"] == False
    assert "Sarah" not in str(result)  # No names exposed
```

---

## File Structure

```
chefs/services/sous_chef/tools/
├── __init__.py
├── categories.py          # Add SENSITIVE category
├── loader.py              # Integrate wrapper
├── sensitive_wrapper.py   # NEW: Channel-aware wrapper
└── sensitive_config.py    # NEW: Define what's sensitive
```

---

## Testing Strategy

### Unit Tests
- Category definitions
- Wrapper behavior per channel
- Loader integration

### Integration Tests
- End-to-end: Telegram message asking about allergies
- End-to-end: Web request for same data works

### Manual Verification
- Send "any clients with allergies?" via Telegram
- Should get redirect message, not data

---

## Rollout Plan

1. Merge to `feature/sensitive-data-handling` branch
2. Deploy to staging
3. Manual test Telegram flow
4. Merge to main
5. Monitor for issues

---

## Security Considerations

- **Default deny**: Unknown tools default to restricted on external channels
- **Audit logging**: Log when sensitive data is blocked (for debugging)
- **No client-side bypass**: Restrictions enforced server-side

---

## Future Enhancements

1. **Granular permissions**: Per-chef settings for what to share
2. **Encryption**: End-to-end encrypted Telegram option
3. **Consent**: Customer consent for data sharing preferences
