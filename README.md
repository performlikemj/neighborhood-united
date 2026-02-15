# sautai

**The operating system for personal chefs.**

sautai gives personal chefs a single hub to manage clients, plan meals, handle payments, and grow their business — powered by an AI sous chef that knows every family's dietary needs, allergies, and preferences.

## Why sautai

Running a personal chef business means juggling client preferences, household allergies, meal prep logistics, grocery lists, invoicing, and communication — often across spreadsheets, texts, and memory. sautai brings it all into one place and pairs you with an AI sous chef that handles the mental load so you can focus on cooking.

## For Chefs

### Chef Hub — Your Dashboard

The Chef Hub is the command center for your business:

- **Client Management** — View all your families in one place: contact info, dietary preferences, allergies, household members, and interaction history. Add manual leads, track prospects through your pipeline, and convert them into paying clients.
- **Orders & Fulfillment** — See upcoming orders with delivery dates, dietary requirements, and prep schedules. Coordinate meal prep across multiple families.
- **Kitchen** — Manage your ingredients with full nutritional data, build dishes from them, and feature your best work in your public profile gallery.
- **Payments** — Connect your Stripe account, generate shareable payment links with household-size pricing tiers, and support recurring or one-time payments across 11 currencies.
- **Analytics** — Track revenue over time, monitor business trends, and see upcoming scheduled orders.
- **Telegram Notifications** — Link your Telegram account to get instant push notifications for new orders, messages, and updates.

### Sous Chef — Your AI Assistant

The Sous Chef is an AI assistant built specifically for personal chefs. It knows your clients and can:

- **Summarize family dietary needs** — Pull up a complete view of any family's restrictions, allergies, and preferences instantly.
- **Check recipe compliance** — Validate a recipe against a family's dietary requirements before you cook.
- **Suggest personalized menus** — Generate menu ideas based on a family's history, preferences, and past orders.
- **Scale recipes** — Auto-adjust ingredient quantities for different household sizes.
- **Estimate prep time** — Calculate total prep and cook time for a full menu.
- **Track client relationships** — Add notes about families (preferences, feedback, observations) and review order history.
- **Navigate your dashboard** — Jump to any section, prefill forms, or scaffold new meals through conversation.

The Sous Chef maintains conversation context per family, so you can pick up where you left off.

## For Customers

Customers use sautai to find local chefs and simplify their own meal planning:

- **Chef Discovery** — Browse verified local chefs by location, view profiles, galleries, certifications, and reviews.
- **AI Meal Planning** — Get personalized weekly meal plans from MJ, the AI consultant, with the option to swap in chef-prepared meals.
- **Shopping Lists** — Auto-generate Instacart shopping lists from your meal plan (US/Canada).
- **Pantry Tracking** — Manage pantry items to reduce food waste and save money.
- **Nutrition Guidance** — Ask MJ about diet, nutrition, recipes, and cooking.
- **Household Profiles** — Set dietary preferences, allergies, and goals for each household member.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.2, Django REST Framework, Django Channels |
| Frontend | React 18, Vite, React Router v6, TanStack Query |
| iOS | SwiftUI with async/await |
| Database | PostgreSQL + pgvector (embeddings) |
| AI | OpenAI Agents SDK, Groq via LiteLLM |
| Payments | Stripe (embedded payment links) |
| Notifications | Telegram Bot API |
| Storage | Azure Blob Storage |
| Task Scheduling | QStash |
| Real-time | WebSockets via Channels Redis |

## Getting Started

```bash
# Clone and set up
git clone https://github.com/performlikemj/sautai.git
cd sautai

# Backend
python -m venv .sautai
source .sautai/bin/activate
pip install -r requirements.txt
cp dev.env .env                     # Configure your environment variables
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver          # http://localhost:8000

# Frontend
cd frontend
pnpm install
npm start                           # http://localhost:5173
```

## License

GNU General Public License v3.0 — see [LICENSE.md](LICENSE.md).
