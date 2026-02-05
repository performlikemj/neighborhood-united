# Manual Test Plan: Chef Onboarding Improvements

**Branch:** `feature/chef-onboarding-improvements`  
**Date:** 2026-02-05  
**Features:** Chef approval email, certification expiry tracking

---

## Prerequisites

1. PostgreSQL running on port 5433
2. Django migrations applied: `python manage.py migrate`
3. Email backend configured (or use console backend for testing)
4. At least one user account that can become a chef

---

## Test 1: Chef Approval Email

### Setup
1. Create a regular user account (or use existing non-chef user)
2. Have user submit a chef application via the API or frontend

### Test Steps

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1.1 | Go to Django Admin → Chef Requests | See pending chef request |
| 1.2 | Click on the request, check "is_approved", save | Request saves successfully |
| 1.3 | Check admin messages | See "Successfully approved... Approval email sent!" |
| 1.4 | Check user's email inbox | Receive welcome email with: |
|     | | - 🎉 "You're Approved!" header |
|     | | - 4-step "What to do next" guide |
|     | | - "Go to Your Chef Dashboard" button |
| 1.5 | Click dashboard link in email | Opens chef dashboard |

### Test with Console Email Backend
If using console backend, check terminal output for email HTML.

```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

### Bulk Approval Test

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1.6 | Select multiple pending requests in admin | Checkboxes selected |
| 1.7 | Action → "Approve selected chef requests" | All approved |
| 1.8 | Check admin messages | "Successfully approved X chef request(s). Approval emails sent!" |

---

## Test 2: Food Handler Certificate Fields

### Setup
1. Have an approved chef account
2. Access Django Admin → Chefs → Chef

### Test Steps

| Step | Action | Expected Result |
|------|--------|-----------------|
| 2.1 | Open a Chef record in admin | See new fields: |
|     | | - food_handlers_cert (checkbox) |
|     | | - food_handlers_cert_number (text) |
|     | | - food_handlers_cert_expiry (date) |
|     | | - food_handlers_cert_verified_at (datetime) |
| 2.2 | Check food_handlers_cert | Checkbox checked |
| 2.3 | Enter cert number: "FH-12345-CA" | Saves successfully |
| 2.4 | Set expiry: 20 days from today | Saves successfully |
| 2.5 | Save and reload | All values persisted |

---

## Test 3: Certification Expiry Notifications

### Setup
1. Chef with `food_handlers_cert = True`
2. Chef with proactive settings enabled (`enabled = True`)
3. Chef with `notify_cert_expiry = True`

### Test Cases

#### 3A: No notification when cert is far from expiry

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3A.1 | Set `food_handlers_cert_expiry` = today + 60 days | Saved |
| 3A.2 | Run proactive check (see command below) | No cert_expiry notification created |

#### 3B: Warning notification (30 days)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3B.1 | Set `food_handlers_cert_expiry` = today + 25 days | Saved |
| 3B.2 | Run proactive check | Notification created with: |
|      | | - Type: `cert_expiry` |
|      | | - Title contains "25 days" |
|      | | - action_context.urgency = "warning" |

#### 3C: Urgent notification (7 days)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3C.1 | Set `food_handlers_cert_expiry` = today + 5 days | Saved |
| 3C.2 | Clear previous notifications for this chef | Cleared |
| 3C.3 | Run proactive check | Notification created with: |
|      | | - Title contains "5 days" and ⚠️ |
|      | | - action_context.urgency = "urgent" |

#### 3D: Expired notification

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3D.1 | Set `food_handlers_cert_expiry` = today - 5 days | Saved |
| 3D.2 | Clear previous notifications | Cleared |
| 3D.3 | Run proactive check | Notification created with: |
|      | | - Title contains "expired" and 🚨 |
|      | | - action_context.urgency = "expired" |

#### 3E: Insurance expiry (same logic)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3E.1 | Set `insured = True`, `insurance_expiry` = today + 20 days | Saved |
| 3E.2 | Run proactive check | Notification with "insurance" in title |
|      | | action_context.cert_type = "insurance" |

#### 3F: Deduplication

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3F.1 | Run proactive check twice | First run: notification created |
|      | | Second run: no duplicate created |

### Running Proactive Check Manually

```python
# Django shell
from chefs.tasks.proactive_engine import run_proactive_check
result = run_proactive_check()
print(result)  # {'processed': X, 'notifications': Y}

# Or check specific chef
from chefs.tasks.proactive_engine import check_certification_expiry
from chefs.models import ChefProactiveSettings
settings = ChefProactiveSettings.objects.get(chef_id=<CHEF_ID>)
notifications = check_certification_expiry(settings)
print(notifications)
```

### Checking Notifications

```python
# Django shell
from chefs.models import ChefNotification
ChefNotification.objects.filter(
    chef_id=<CHEF_ID>,
    notification_type='cert_expiry'
).values('title', 'message', 'action_context', 'created_at')
```

---

## Test 4: Proactive Settings Toggle

### Test Steps

| Step | Action | Expected Result |
|------|--------|-----------------|
| 4.1 | Set chef's `notify_cert_expiry = False` | Saved |
| 4.2 | Set cert to expire in 20 days | Saved |
| 4.3 | Run proactive check | NO cert_expiry notification created |
| 4.4 | Set `notify_cert_expiry = True` | Saved |
| 4.5 | Run proactive check | Notification IS created |

---

## Test 5: Test Settings (PostgreSQL)

### Verify Test Infrastructure

```bash
cd neighborhood-united
DJANGO_SETTINGS_MODULE=hood_united.test_settings \
  .venv/bin/pytest chefs/tests/test_cert_expiry.py -v
```

| Expected | Result |
|----------|--------|
| 15 tests | All pass ✅ |
| Database | PostgreSQL (not SQLite) |

---

## Regression Tests

Run full proactive test suite to ensure no regressions:

```bash
DJANGO_SETTINGS_MODULE=hood_united.test_settings \
  .venv/bin/pytest chefs/tests/test_proactive_engine.py \
                   chefs/tests/test_proactive_models.py \
                   chefs/tests/test_cert_expiry.py -v
```

| Expected | Result |
|----------|--------|
| 100 tests | All pass ✅ |

---

## Sign-off Checklist

- [ ] Chef approval email sends correctly
- [ ] Email template renders properly (no broken images/styles)
- [ ] Cert expiry fields save and persist
- [ ] 30-day warning notification works
- [ ] 7-day urgent notification works
- [ ] Expired notification works
- [ ] Insurance expiry notification works
- [ ] Deduplication prevents spam
- [ ] notify_cert_expiry toggle respected
- [ ] All automated tests pass

---

## Notes

- **Email configuration:** Ensure `DEFAULT_FROM_EMAIL` and `FRONTEND_URL` are set in production
- **Celery:** The proactive engine runs hourly via Celery Beat in production
- **Admin:** Approval email is triggered from Django Admin only (not API)
