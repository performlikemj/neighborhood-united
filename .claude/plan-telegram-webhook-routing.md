# Plan: Route Telegram Webhook via Azure Static Web Apps

## Problem
- Telegram sends POST to `https://sautai.com/chefs/api/telegram/webhook/`
- `sautai.com` points to Azure Static Web App (frontend)
- SWA serves `index.html` for all routes → returns 405 for POST
- Django backend is at `sautai-django-westus2.redcliff-686826f3.westus2.azurecontainerapps.io`

## Constraint Discovered
**Azure SWA Linked Backends only proxy routes starting with `/api/`**

From Microsoft docs:
> "The endpoint on the container app must have the `/api` prefix, since Static Web Apps matches requests made to `/api` and proxies the entire path to the linked resource."

Our current webhook path `/chefs/api/telegram/webhook/` does NOT start with `/api/` - it starts with `/chefs/`.

## Options

### Option A: Move webhook to `/api/` prefix (Recommended)
Add a new URL route in Django at `/api/telegram/webhook/` that points to the same view.

**Pros:**
- Uses Azure's native SWA → Container App linking
- Single public domain (sautai.com)
- No infrastructure changes needed

**Cons:**
- Requires adding a URL route in Django
- Need to re-register webhook with Telegram

### Option B: Use direct Container App URL for webhook only
Register Telegram webhook with:
`https://sautai-django-westus2.redcliff-686826f3.westus2.azurecontainerapps.io/chefs/api/telegram/webhook/`

**Pros:**
- No code changes
- Works immediately

**Cons:**
- Exposes backend Azure FQDN
- Inconsistent with other API routing

### Option C: Deploy frontend with nginx (container)
Replace Azure SWA with a containerized nginx that uses the existing nginx.conf.

**Pros:**
- Uses existing nginx.conf proxy rules
- Full control over routing

**Cons:**
- Significant infrastructure change
- Lose SWA benefits (auto SSL, CDN, etc.)

---

## Recommended Plan: Option A

### Step 1: Add `/api/telegram/webhook/` route to Django
Edit `hood_united/urls.py` to add:
```python
from chefs.api.telegram_webhook import telegram_webhook

urlpatterns = [
    # ... existing routes ...

    # Telegram webhook (for Azure SWA linked backend - must start with /api/)
    path('api/telegram/webhook/', telegram_webhook, name='telegram_webhook_swa'),
]
```

### Step 2: Deploy Django changes
Push to main and let CI/CD deploy.

### Step 3: Link Container App to Static Web App
```bash
az staticwebapp backends link \
  --name sautai-frontend \
  --resource-group sautAI \
  --backend-resource-id "/subscriptions/63ceeeac-fe3f-4bcb-b6d2-b7aa7fd6bf52/resourceGroups/sautAI/providers/Microsoft.App/containerapps/sautai-django-westus2" \
  --backend-region "westus2"
```

### Step 4: Update Telegram webhook URL
```bash
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://sautai.com/api/telegram/webhook/", "secret_token": "'${SECRET}'"}'
```

### Step 5: Verify
```bash
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

---

## Files to Modify
1. `hood_united/urls.py` - Add `/api/telegram/webhook/` route

## Commands to Run
1. `git add && git commit && git push` - Deploy Django
2. `az staticwebapp backends link ...` - Link backend
3. `curl ... setWebhook` - Update Telegram
4. `curl ... getWebhookInfo` - Verify

## Rollback
If issues occur:
- Unlink backend: `az staticwebapp backends unlink --name sautai-frontend --resource-group sautAI`
- Revert to direct URL for webhook
