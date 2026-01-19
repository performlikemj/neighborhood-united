# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

sautai is an AI-powered meal planning platform that connects users with local chefs. It features MJ, an AI assistant for nutrition and meal planning guidance. The platform serves customers (meal planning, chef discovery), chefs (services, order management), and administrators (verification, platform management).

## Commands

### Backend (Django)
```bash
python manage.py runserver          # Development server (port 8000)
python manage.py migrate            # Run migrations
python manage.py makemigrations     # Create new migrations
pytest                              # Run all tests (uses --reuse-db)
pytest path/to/test_file.py::test_name  # Run single test
pytest -k "keyword"                 # Run tests matching keyword
```

### Frontend (React/Vite)
```bash
cd frontend
pnpm install                        # Install dependencies (preferred) or npm install
npm start                           # Dev server (port 5173)
npm run build                       # Production build
npm run lint                        # ESLint
npm run test                        # Run E2E tests (Playwright)
npm run audit                       # Audit API paths and React hooks
```

### Health Check
```
GET /healthz/                       # Returns "ok" for load balancers
```

## Architecture

### Tech Stack
- **Backend**: Django 5.2 + Django REST Framework + Django Channels (WebSockets)
- **Frontend**: React 18 + Vite + React Router v6 + TanStack Query
- **Database**: PostgreSQL with pgvector extension (embeddings)
- **Task Scheduling**: QStash (replaces deprecated Celery Beat)
- **Auth**: JWT (SimpleJWT) for API, session auth for admin
- **Payments**: Stripe (embedded payment links)
- **Storage**: Azure Blob Storage (production), local (development)

### Django Apps
| App | Purpose |
|-----|---------|
| `chefs` | Chef profiles, verification, services, resource planning |
| `chef_services` | Service tier management and pricing |
| `meals` | Meal planning, generation, embeddings, chef meal events |
| `custom_auth` | Authentication, JWT, user roles |
| `customer_dashboard` | Customer dashboard and order management |
| `local_chefs` | Location-based features, postal codes |
| `messaging` | Real-time WebSocket messaging |
| `memberships` | Subscription management |
| `crm` | Customer relationship management |

### Frontend Structure
```
frontend/src/
  ├── components/     # Reusable React components
  ├── pages/          # Page components (Home, ChefDashboard, MealPlans, etc.)
  ├── context/        # React contexts for state management
  ├── hooks/          # Custom React hooks
  ├── api/            # API client and endpoint definitions
  ├── config/         # Feature flags and configuration
  └── styles.css      # Unified stylesheet with CSS variables
```

### API URL Structure
- `/api/` - QStash cron triggers and general API
- `/auth/` - Authentication endpoints
- `/chefs/` - Chef-related endpoints
- `/meals/` - Meal planning endpoints
- `/chef/api/dashboard/` - Chef dashboard API
- `/services/` - Chef services
- `/messaging/` - Messaging endpoints

## Key Patterns

### CSS Theming
Uses CSS variables for light/dark mode support. Key variables:
- `--text`, `--muted`, `--surface`, `--surface-2`, `--border`
- Status colors: `--success`, `--warning`, `--danger`, `--info`, `--pending` (with `-bg` variants)
- Dark mode via `[data-theme="dark"]` selector

### Feature Flags
- `LEGACY_MEAL_PLAN_ENABLED` - Controls deprecated meal planning stack
- `MEAL_PLAN_EMAIL_NOTIFICATIONS_ENABLED` - Email notification toggle

### Testing
- Backend: pytest with `--reuse-db`, auto-mocked OpenAI client in `conftest.py`
- Frontend: Playwright for E2E tests, custom audit scripts

### Task Execution
QStash handles scheduled tasks via webhook endpoints in `api/cron_triggers.py`. This replaces the deprecated Celery Beat pattern.

## Continuity Ledger

This project uses `CONTINUITY.md` for maintaining context across sessions. See `AGENTS.md` for the continuity ledger pattern - update the ledger when goals, constraints, decisions, or progress state changes.
