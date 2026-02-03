# Sous Chef + OpenAI Agents SDK + LINE MCP Quick Start

## Overview

This guide shows how to run Sous Chef with:
- **OpenAI Agents SDK** - handles agent loop, tools, tracing
- **LINE MCP Server** - enables LINE messaging as agent tools

## Prerequisites

1. Python 3.10+
2. Node.js 18+ (for LINE MCP server)
3. LINE Official Account with Messaging API enabled
4. LINE Channel Access Token

## Step 1: Install Dependencies

```bash
# In your virtualenv
pip install openai-agents

# Verify
python -c "from agents import Agent; print('✅ Agents SDK installed')"
```

## Step 2: Set Environment Variables

```bash
# OpenAI API key (required for Agents SDK)
export OPENAI_API_KEY="sk-..."

# LINE credentials
export LINE_CHANNEL_ACCESS_TOKEN="your-line-channel-token"

# Optional: Default LINE user to message
export LINE_DESTINATION_USER_ID="U..."
```

## Step 3: Test LINE MCP Server Standalone

```bash
# This spawns the LINE MCP server
npx @line/line-bot-mcp-server

# You should see it start. Ctrl+C to stop.
# The Agents SDK will spawn this automatically when needed.
```

## Step 4: Test the POC

```python
# In Django shell or script
import asyncio
from chefs.services.sous_chef_agents_poc import create_sous_chef_agent, run_sous_chef

# Create agent with LINE enabled
agent = create_sous_chef_agent(
    chef_id=1,  # Your test chef ID
    enable_line=True
)

# Test basic functionality
async def test():
    # Test without LINE
    response = await run_sous_chef(agent, "What are my upcoming orders?")
    print(response)
    
    # Test with LINE (requires valid LINE_DESTINATION_USER_ID)
    # response = await run_sous_chef(
    #     agent, 
    #     "Send a LINE message to user U... saying 'Hello from Sous Chef!'"
    # )
    # print(response)

asyncio.run(test())
```

## Step 5: Test from Django View (Sync)

```python
from chefs.services.sous_chef_agents_poc import create_sous_chef_agent, run_sous_chef_sync

def sous_chef_chat_view(request, chef_id):
    message = request.POST.get('message')
    
    agent = create_sous_chef_agent(
        chef_id=chef_id,
        enable_line=True
    )
    
    response = run_sous_chef_sync(agent, message)
    
    return JsonResponse({"response": response})
```

## Available LINE Tools (via MCP)

Once LINE MCP is enabled, the agent can use:

| Tool | Description |
|------|-------------|
| `push_text_message` | Send text to a LINE user |
| `push_flex_message` | Send rich card messages |
| `broadcast_text_message` | Message all followers |
| `get_profile` | Get user's LINE profile |
| `create_rich_menu` | Create button menus |
| `get_message_quota` | Check message limits |

Example agent prompts:
- "Send a LINE message to user U123 saying their order is ready"
- "Broadcast a message to all my followers about tomorrow's special"
- "Create a rich menu with options for Order, Schedule, and Contact"

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Django Backend                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Sous Chef Agent                     │   │
│  │  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │ Your Tools  │  │ LINE MCP Server (stdio) │  │   │
│  │  │ - orders    │  │ - push_text_message     │  │   │
│  │  │ - dishes    │  │ - push_flex_message     │  │   │
│  │  │ - prefs     │  │ - broadcast             │  │   │
│  │  └─────────────┘  └─────────────────────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                    Agent Loop                           │
│              (handled by Agents SDK)                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │     LINE Platform     │
              │   (via MCP Server)    │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Chef's LINE App     │
              │   Customer's LINE     │
              └───────────────────────┘
```

## Next Steps

1. **Test POC** - Verify basic agent + LINE works
2. **Add more tools** - Port remaining Sous Chef tools
3. **Add sessions** - Use SDK sessions for conversation memory
4. **Add tracing** - Enable OpenAI tracing for debugging
5. **Full migration** - Replace current SousChefAssistant class

## Troubleshooting

### "openai-agents not found"
```bash
pip install openai-agents
```

### "LINE MCP server failed to start"
```bash
# Test manually first
npx @line/line-bot-mcp-server
# Check Node.js version (18+ required)
node --version
```

### "OPENAI_API_KEY not set"
The Agents SDK requires an OpenAI API key even when using other models.
```bash
export OPENAI_API_KEY="sk-..."
```

### "LINE message failed"
- Check `LINE_CHANNEL_ACCESS_TOKEN` is valid
- Verify the user ID format (starts with U)
- Check LINE Official Account message quota
