# NIVORA

NIVORA is a production-oriented operations workspace for procurement, inventory, fulfillment, and analytics. It is built as a Django modular monolith with API-first workflows, workspace-aware RBAC, OTP onboarding, JWT-backed API access, and a dark industrial SaaS interface optimized for operators.

## Product Scope

- Domain: ERP / SaaS operations workspace
- Primary users: workspace owners, admins, operators, analysts, and customer-facing accounts
- Core problem: fragmented purchase, stock, QC, sales, dispatch, and reporting workflows spread across disconnected tools

## Modules

- `apps.accounts`: custom users, workspaces, memberships, OTP onboarding, JWT issuance
- `apps.operations`: suppliers, products, purchase orders, receipts, QC, inventory, sales orders, shipments, invoices, activity
- `apps.dashboard`: KPI aggregation, trend analytics, activity feed
- `apps.notifications`: in-app notifications and polling feed
- `apps.search`: command-palette global search
- `core`: shared audit model, RBAC, middleware, context, mixins
- `services`: business logic for auth, operations, search, dashboard, reports, notifications
- `api`: versioned JSON endpoints

## Workflow

1. A user requests an OTP and joins or creates a workspace.
2. Admins manage suppliers and products.
3. Buyers create purchase orders with structured line items.
4. Warehouse teams receive goods into pending QC lots.
5. QC approves or rejects lots, and approved quantity updates stock.
6. Customer orders are created against the live catalog.
7. Ready orders dispatch with carrier tracking and invoice generation.
8. Dashboard, search, and notification feeds reflect activity across the workspace.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Architecture Notes

- Modular monolith with explicit service layer
- SQLite is the default local database, while `DATABASE_URL` supports PostgreSQL in production
- Redis and Celery are production-ready via environment configuration, with graceful local fallbacks
- JWT utilities use HS256 tokens without adding a hard dependency beyond Django
- Search uses PostgreSQL full-text when available and falls back to scoped `icontains` matching locally

Detailed architecture, schema, and API notes live in [docs/architecture.md](/Users/mahi../Desktop/NIVORA/docs/architecture.md).
