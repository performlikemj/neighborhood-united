# n8n Decommissioning Plan

## Executive Summary

**STATUS: ✅ READY FOR DELETION**

All required n8n functionality has been migrated or deprecated. The n8n container can be safely deleted from Azure.

---

## What Was Migrated

### ✅ Core Authentication Emails

These flows now use Django's `EmailMultiAlternatives` via `utils/email.py`:

| Flow | Location | Status |
|------|----------|--------|
| Password Reset | `custom_auth/views.py` | ✅ Migrated |
| User Registration | `custom_auth/views.py` | ✅ Migrated |
| Profile Update / Email Change | `custom_auth/views.py` | ✅ Migrated |
| Resend Activation | `custom_auth/views.py` | ✅ Migrated |
| Onboarding Completion | `custom_auth/views.py` | ✅ Migrated |
| Assistant Reply Emails | `meals/meal_assistant_implementation.py` | ✅ Migrated |

### ❌ Deprecated (Not Migrated - Not Required)

The following features were part of the user-focused implementation and are **not required** for the chef CRM:

| Feature | Location | Status |
|---------|----------|--------|
| Email Aggregation | `customer_dashboard/` | ❌ Deprecated |
| Pending Message Acknowledgment | `custom_auth/views.py` | ❌ Deprecated |
| Email Assistant Sessions | `customer_dashboard/` | ❌ Deprecated |

**Note:** Code referencing `N8N_EMAIL_REPLY_WEBHOOK_URL` in these files will safely no-op when the environment variable is empty/unset.

### ⚠️ Error Reporting

**N8N_TRACEBACK_URL** references have been replaced:
- Core files updated to use `logger.exception()` directly
- Remaining references will safely no-op (empty URL = no-op)
- Future: Integrate Sentry for production error tracking

---

## Error Reporting: Current State and Future Plan

### Current State

Error reporting now uses Python's standard logging:
- All critical paths use `logger.exception()` or `logger.error()`
- Error context is logged with tracebacks
- Logs are available in Azure Container Apps log stream

### Future: Sentry Integration

A centralized error reporting utility has been created at `utils/error_reporting.py`.

**To integrate Sentry:**

1. Install sentry-sdk:
   ```bash
   pip install sentry-sdk
   ```

2. Add environment variable:
   ```bash
   SENTRY_DSN=https://your-dsn@sentry.io/project
   ```

3. Uncomment Sentry initialization in `hood_united/settings.py`:
   ```python
   import sentry_sdk
   from sentry_sdk.integrations.django import DjangoIntegration
   from sentry_sdk.integrations.celery import CeleryIntegration
   
   if os.getenv('SENTRY_DSN'):
       sentry_sdk.init(
           dsn=os.getenv('SENTRY_DSN'),
           integrations=[DjangoIntegration(), CeleryIntegration()],
           traces_sample_rate=0.1,
           send_default_pii=False,
       )
   ```

4. Update `utils/error_reporting.py` to capture to Sentry

---

## Production Cleanup Commands

### Step 1: Remove Environment Variables

```bash
# Remove from Django backend
az containerapp update \
  --name sautai-backend \
  --resource-group hood-united \
  --remove-env-vars \
    N8N_TRACEBACK_URL \
    N8N_ORDER_EVENTS_WEBHOOK_URL \
    N8N_PW_RESET_URL \
    N8N_UPDATE_PROFILE_URL \
    N8N_REGISTER_URL \
    N8N_RESEND_URL \
    N8N_EMAIL_REPLY_WEBHOOK_URL

# Remove from Celery worker
az containerapp update \
  --name sautai-celery-worker \
  --resource-group hood-united \
  --remove-env-vars \
    N8N_TRACEBACK_URL \
    N8N_ORDER_EVENTS_WEBHOOK_URL \
    N8N_EMAIL_REPLY_WEBHOOK_URL

# Remove from Celery beat
az containerapp update \
  --name sautai-celery-beat \
  --resource-group hood-united \
  --remove-env-vars \
    N8N_TRACEBACK_URL \
    N8N_ORDER_EVENTS_WEBHOOK_URL \
    N8N_EMAIL_REPLY_WEBHOOK_URL
```

### Step 2: Delete n8n Container

**⚠️ Run only after Step 1 completes successfully**

```bash
# Delete n8n container
az containerapp delete \
  --name n8n \
  --resource-group hood-united \
  --yes

# Verify deletion
az containerapp list \
  --resource-group hood-united \
  --output table
```

---

## Verification Checklist

After running the cleanup commands:

- [ ] Django backend starts without errors
- [ ] Celery worker starts without errors
- [ ] Celery beat starts without errors
- [ ] Registration email sends successfully
- [ ] Password reset email sends successfully
- [ ] Email change verification sends successfully
- [ ] No n8n-related errors in logs

### Monitor Logs

```bash
# Check backend logs for errors
az containerapp logs show \
  --name sautai-backend \
  --resource-group hood-united \
  --follow

# Filter for email-related messages
az containerapp logs show \
  --name sautai-backend \
  --resource-group hood-united \
  --follow | grep -i "email\|smtp"
```

---

## Expected Cost Savings

After n8n container deletion: **$15-40/month**

---

## Rollback Plan (If Needed)

If critical issues are discovered:

1. **Re-deploy n8n** from Azure Container Registry (if image exists)
2. **Re-add environment variables** via Azure CLI
3. **Git revert** code changes:
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

**Note:** Keep n8n container credentials documented before deletion.

---

## Summary

| Component | Status |
|-----------|--------|
| Auth emails | ✅ Migrated to Django |
| customer_dashboard emails | ❌ Deprecated (not required) |
| Error reporting | ✅ Using Python logging |
| n8n container | ⏳ Ready for deletion |
| Sentry integration | 📋 TODO (see utils/error_reporting.py) |

---

**Last Updated:** December 2024
**Contact:** michaeljones (owner)
