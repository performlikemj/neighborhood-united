# URL Path Conventions

This document defines the URL path conventions to prevent routing mismatches between frontend, nginx, and Django.

## The Golden Rules

### 1. Django App Prefixes Use UNDERSCORES

Django apps are named with underscores. The URL prefix **must match exactly**.

```
✅ CORRECT                     ❌ WRONG
/customer_dashboard/api/...    /customer-dashboard/api/...
/local_chefs/api/...           /local-chefs/api/...
```

### 2. URL Path Segments Can Use HYPHENS

Within the URL path (after the app prefix), hyphens are fine:

```
✅ CORRECT
/customer_dashboard/api/my-chefs/
/meals/api/chef-meal-events/
/chefs/api/by-username/
```

### 3. Every Frontend API Prefix Must Be in Nginx

The nginx proxy location pattern must include ALL prefixes used by the frontend:

```nginx
# nginx.conf
location ~ ^/(auth|meals|chefs|reviews|customer_dashboard|services|local_chefs)/ {
    proxy_pass ...
}
```

If you add a new Django app, **you must add it to nginx too**.

## Current Prefixes

| Prefix | Django App | Description |
|--------|------------|-------------|
| `auth` | `custom_auth` | Authentication, user details |
| `meals` | `meals` | Meal plans, orders, chef meals |
| `chefs` | `chefs` | Chef profiles, availability |
| `reviews` | `reviews` | Meal reviews |
| `customer_dashboard` | `customer_dashboard` | Customer portal, AI assistant |
| `services` | `chef_services` | Offerings, connections, orders |
| `local_chefs` | `local_chefs` | Service areas, geo lookup |

## Before You Add a New API Route

### Checklist

1. **Is the prefix in nginx.conf?**
   - Check `location ~ ^/(...)/ {` pattern
   - If not, add it

2. **Are you using the correct case?**
   - Django app prefixes: underscores (`customer_dashboard`)
   - URL segments: hyphens are OK (`/api/my-chefs/`)

3. **Run the audit scripts:**
   ```bash
   node scripts/audit-api-paths.mjs
   node scripts/audit-react-hooks.mjs
   pnpm test
   ```

## Common Mistakes

### Mistake 1: Hyphen in App Prefix

```javascript
// ❌ WRONG - Django app uses underscore
api.get('/customer-dashboard/api/my-chefs/')

// ✅ CORRECT
api.get('/customer_dashboard/api/my-chefs/')
```

### Mistake 2: Wrong App Name

```javascript
// ❌ WRONG - The Django app is 'services', not 'chef-services'
api.post('/chef-services/orders/123/checkout/')

// ✅ CORRECT
api.post('/services/orders/123/checkout/')
```

### Mistake 3: Missing Nginx Proxy

```javascript
// Frontend calls /local_chefs/api/areas/...
// But nginx.conf doesn't proxy /local_chefs/
// Result: 404 in production!

// FIX: Add 'local_chefs' to nginx location pattern
```

## CI Integration

The following scripts run in CI to catch these issues:

```bash
# Check API paths match nginx
node scripts/audit-api-paths.mjs

# Check React hooks for infinite loop patterns
node scripts/audit-react-hooks.mjs

# Run all tests including path integrity
pnpm test
```

These will fail the build if issues are detected.

## Quick Reference: File Locations

| Check | File |
|-------|------|
| Nginx proxy rules | `frontend/nginx.conf` |
| Django URL routes | `hood_united/urls.py` |
| Frontend API calls | `frontend/src/**/*.{js,jsx}` |
| Path audit script | `frontend/scripts/audit-api-paths.mjs` |
| Hooks audit script | `frontend/scripts/audit-react-hooks.mjs` |
| Integrity tests | `frontend/tests/apiPathsIntegrity.test.mjs` |
