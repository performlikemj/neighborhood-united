# Agents SDK Troubleshooting Guide

Common issues and solutions when working with the OpenAI Agents SDK integration for Sous Chef.

---

## Navigation Actions Not Working

**Symptoms:**
- User asks "take me to the clients tab" but nothing happens
- Raw JSON appears in chat instead of navigation
- Button appears but doesn't auto-navigate

### Root Causes & Fixes

#### 1. Parameter Mismatch in Tool Wrapper

**Problem:** The Agents SDK tool wrapper was passing `{"tab_name": tab_name}` but the underlying function `_navigate_to_dashboard_tab` expects `args.get("tab")`.

**File:** `chefs/services/sous_chef/tools/agents_tools.py`

**Fix:**
```python
# Wrong
return _navigate_to_dashboard_tab(
    {"tab_name": tab_name},  # WRONG KEY
    ToolContext.chef, ToolContext.customer, ToolContext.lead
)

# Correct
return _navigate_to_dashboard_tab(
    {"tab": tab_name},  # CORRECT KEY
    ToolContext.chef, ToolContext.customer, ToolContext.lead
)
```

#### 2. Tool Results Not Captured (Hook Issue)

**Problem:** The Agents SDK's `Runner.run_sync()` executes tools internally. The `final_output` is the LLM's text response, NOT the raw tool results. The frontend needs action blocks from tool results to render navigation buttons.

**Solution:** Implement `RunHooksBase` to capture tool results with `render_as_action: True`.

**File:** `chefs/services/sous_chef/agents_service.py`

```python
from agents.lifecycle import RunHooksBase

class ActionCaptureHooks(RunHooksBase):
    """Captures action-type tool results for frontend rendering."""

    def __init__(self):
        self.captured_actions = []

    async def on_tool_end(self, context, agent, tool, result) -> None:
        """Capture tool results that should render as actions."""
        # Handle result - it may be a dict or a JSON string
        data = None
        if isinstance(result, dict):
            data = result
        elif isinstance(result, str):
            try:
                data = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                return

        if isinstance(data, dict) and data.get("render_as_action"):
            self.captured_actions.append(data)
```

**Important:** Tool results can be Python dicts, not just JSON strings. Don't assume `str(result)` will give valid JSON.

#### 3. Auto-Navigation Not Triggering

**Problem:** Navigation worked via button click but didn't auto-navigate when requested.

**Solution:** Add `auto_execute: True` flag to navigation results and handle in frontend.

**Backend:** `meals/sous_chef_tools.py`
```python
return {
    "status": "success",
    "action_type": "navigate",
    "tab": tab,
    "label": f"Go to {tab_label}",
    "render_as_action": True,
    "auto_execute": True  # Auto-navigate without requiring button click
}
```

**Frontend:** `frontend/src/components/StructuredContent.jsx`
```javascript
// Auto-execute actions that have auto_execute: true
useEffect(() => {
  if (!parsed.blocks || !onAction) return

  for (const block of parsed.blocks) {
    if (block?.type === 'action' && block.auto_execute) {
      const actionKey = `${block.action_type}-${block.payload?.tab || ''}`
      if (!executedActionsRef.current.has(actionKey)) {
        executedActionsRef.current.add(actionKey)
        onAction({ action_type: block.action_type, payload: block.payload })
      }
    }
  }
}, [parsed.blocks, onAction])
```

---

## Data Flow for Navigation

```
1. User: "take me to clients"
   ↓
2. Agents SDK calls navigate_to_dashboard_tab tool
   ↓
3. Tool returns: { action_type: "navigate", tab: "clients", render_as_action: True, auto_execute: True }
   ↓
4. ActionCaptureHooks.on_tool_end() captures this result
   ↓
5. _convert_to_blocks() adds action block to response
   ↓
6. Frontend receives: { blocks: [{ type: "text", ... }, { type: "action", auto_execute: true, ... }] }
   ↓
7. StructuredContent useEffect detects auto_execute and calls onAction
   ↓
8. SousChefPage.handleSousChefAction navigates to /chefs/dashboard?tab=clients
```

---

## Key Files

| File | Purpose |
|------|---------|
| `chefs/services/sous_chef/agents_service.py` | Main service with hooks, converts tool results to blocks |
| `chefs/services/sous_chef/tools/agents_tools.py` | Agents SDK tool wrappers |
| `meals/sous_chef_tools.py` | Underlying tool implementations |
| `frontend/src/components/StructuredContent.jsx` | Renders action blocks, handles auto-execute |
| `frontend/src/pages/SousChefPage.jsx` | Navigation handler |

---

## Testing Navigation

```bash
# Test in Django shell
python manage.py shell -c "
from chefs.services.sous_chef.agents_service import AgentsSousChefService
from chefs.models import Chef

chef = Chef.objects.first()
service = AgentsSousChefService(chef_id=chef.id, channel='web')
result = service.send_structured_message('take me to the clients tab')

# Check for action block with auto_execute
for block in result['content']['blocks']:
    if block['type'] == 'action':
        print(f\"Action: {block['action_type']}, Tab: {block['payload']['tab']}, Auto: {block.get('auto_execute')}\")
"
```

---

## Common Mistakes

1. **Forgetting to restart Django server** after Python changes
2. **Not hard-refreshing browser** (`Cmd+Shift+R`) after frontend changes
3. **Assuming tool results are JSON strings** - they're often Python dicts
4. **Missing `onAction` prop** in component chain (SousChefPage → SousChefChat → MessageBubble → StructuredContent)
