# Cosmetics ERP

**Repository:** https://github.com/Bappito/Cosmetics-Project  
**Online app:** not deployed yet. See [Hosting on PythonAnywhere](#hosting-on-pythonanywhere).

A web app for a cosmetics manufacturing company. It brings stock, purchasing, production planning, packaging, batches, traceability and personal what-if scenarios together in one place. The business data lives in a local SQLite database. The app is built with Django.

The interface supports Hebrew (right-to-left) and English (left-to-right). Users sign in, and what they can see and change depends on their role.

## Online access

The app is not deployed yet. It runs on a local computer at http://localhost:8000/. The planned host is PythonAnywhere (free plan); once it is live, its address will be **https://YOUR_USERNAME.pythonanywhere.com/**. The steps are in [Hosting on PythonAnywhere](#hosting-on-pythonanywhere).

## Features

- **Warehouses** — four tabs: raw materials, bulk, packaging, and ready material (finished products). Each shows stock, expiry dates, suppliers, catalog editing, physical count, and ERP import (SAP or Priority CSV/Excel exports). Each row shows its unit (kg, g or units).
- **Stock summary** — totals by warehouse and by item type, plus a check that compares catalog balances with the sum of their active batches.
- **Purchase orders** — two screens: **Purchase orders** (a read-only list of all orders, with search and a status filter) and **Purchase orders management** (edit, review, and receive an order into a warehouse).
- **Purchase planning (MRP)** — works out what to buy from the eight-week plan. Suggestions are rounded to the minimum order quantity and can become draft POs.
- **Product trees (BOM)** — a list of all parent products. Each product opens a tree page with its components, stock, ratio to the parent and how many parent units the stock covers. A bulk component opens to show its own raw materials. Amounts under one kilogram are shown in grams.
- **Pack sizes** — packaging belongs to the finished product, not to the bulk. Make each size (for example 500 ml and 1 L of the same shampoo) its own finished product, with a tree that holds the bulk in grams plus its packaging.
- **Production planning** — one page with three tabs: production line, packaging, and master work. Each shows the weekly plan, component use per SKU (one row per component, with a total across all products that use it), and the cumulative balance.
- **PRR (project readiness)** — one screen with a switch between **Production** (bulk products and their raw materials) and **Packaging** (finished products and their bulk and packaging). It shows the stock for every week (also weeks without production), the users of each component, supplier, open orders and alternatives, and exports the view or a shortage report as CSV. See [Reading the PRR board](#reading-the-prr-board).
- **Week windows** — clicking a week cell in the PRR or production planning opens a floating window beside it, without moving the table. It shows the week's calculation and when purchase orders arrive: date, days away or days late, quantity and order number. It closes with the X button, Escape or a click outside.
- **Batches and traceability** — batch balances and expiry, manual receipts, and consumption links. Production and packaging use batches in FEFO order (earliest expiry first), so several batches of the same material can be used in one run.
- **My simulator** — a private what-if scenario for each user: planned orders by week, with the shortages they would cause. A scenario can be shared for viewing; shared scenarios are read-only for everyone else.
- **Projects, alternative SKUs and shipments** — read-only lists with demo data.
- **Change log, backups and undo** — every save is preceded by a backup, and every backup and undo is written to the change log.
- **Quick command** — add stock with a simple text command such as `תוסיף 5 קילו ל-1001`. This is a local parser; no external AI service is called.
- **Tables** — list tables have a search box, click-to-sort headers, paging, and an export to Excel (CSV, which Excel opens with Hebrew text intact). A row count appears when some rows are hidden. The weekly boards (PRR and planning) are not changed by these tools.
- **Admin menu order** — an admin can move sidebar items up or down. The order applies to every user.
- **Language and units** — Hebrew/English. Item names that are written in two languages show only the current language. Weight can be shown in grams or kilograms.
- **Light, dark and phone** — both themes follow the sidebar switch. On narrow screens the menu becomes one swipeable row, and the PRR hides the products and supplier columns so the weeks fit.

## Requirements

- Python 3.11 or newer
- Packages listed in [`requirements.txt`](./requirements.txt)

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1        # macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then open http://localhost:8000/ and sign in with the superuser account.

On Windows, after the `.venv` folder exists, you can double-click [`run_site.bat`](./run_site.bat). It backs up the database files, switches to `main` and pulls the latest code, installs packages, updates the database, asks for a first user if there is none, and starts the site.

The app uses two SQLite files:

- `cosmetics_3sim_erp.db` — the business data (catalog, batches, purchase orders, planning, scenarios' shared data). On first use it is filled with demo data.
- `django.sqlite3` — users, groups, sessions and personal scenarios.

## Settings

Settings are read from environment variables:

- `DJANGO_SECRET_KEY` — required before hosting.
- `DJANGO_DEBUG` — set to `0` when hosting.
- `DJANGO_ALLOWED_HOSTS` — comma-separated host names, for example `erp.example.com`.
- `ERP_DB_PATH` — the business database file. Defaults to `cosmetics_3sim_erp.db` in the project folder.

## Users and roles

Assign roles in the admin at http://localhost:8000/admin/ under **Groups**. Every screen has a view and an edit permission. Three default groups are created:

- **Admin:** every screen, including profit.
- **Warehouse:** the dashboard, warehouses, the purchase order list, stock summary, shipments, purchase orders, and their own scenarios.
- **Viewer:** the dashboard only, without profit.

Anyone who is not signed in is sent to the login page. Screens a user cannot view are hidden from the sidebar, and direct links to them return "403 Forbidden".

Changing the sidebar order needs the dashboard edit permission, which the Admin group has.

Permissions added after a group was created are not given to it automatically. Check the groups in the admin after an update. Only the Admin group is topped up on each migration.

## Screens

| Screen | URL | What it is for |
| --- | --- | --- |
| Dashboard | `/` | Opening page: expiry and PO counts, what can be packed now, the profit per finished product, and the plan start date. |
| Warehouses | `/inventory/` | Four tabs (raw materials, bulk, packaging, ready material): stock, expiry, suppliers, catalog editing, physical count and ERP import. |
| Purchase orders | `/po-list/` | Read-only list of every order, with search and a status filter. |
| Stock summary | `/stock-summary/` | Totals by warehouse and item type, and the check of catalog balances against batches. |
| Shipments | `/shipments/` | Shipments by customer, shipment type and status (demo data). |
| Projects | `/projects/` | Projects linked to a finished product (demo data). |
| Alternative SKUs | `/alt-skus/` | Replacement SKUs in priority order (demo data). |
| Purchase orders management | `/purchase-orders/` | Edit PO rows and statuses, view arrival weeks, and receive an order into a warehouse. |
| Purchase planning (MRP) | `/mrp/` | What to buy from the eight-week plan, rounded to the minimum order quantity. |
| Batches & traceability | `/batches/` | Batch balances and expiry, manual receipts, and consumption links. |
| Product trees (BOM) | `/bom/` | Product list, tree pages and the tree editor. |
| Production planning | `/production-planning/` | Tabs: 1. production line, 2. packaging, 3. master work. |
| My simulator | `/scenarios/` | Your private what-if scenarios, and scenarios shared with you. |
| PRR | `/prr/` | Readiness with a switch between Production and Packaging. The old address `/prr-packaging/` opens the packaging view. |
| Quick command agent | `/quick-command/` | Add stock using a simple text command. |
| Change log | `/audit/` | Every stock, product-tree and planning change, including undos. |
| Menu order | `/menu-order/` | Admin only: change the order of the sidebar menu. |

The old addresses `/production/`, `/packaging/` and `/master-work/` still open the three planning tabs.

Each change goes through the same steps: check it, review the preview, tick the confirmation, and save. A backup is taken before each save so the last change can be undone.

The sidebar also has language (Hebrew/English), weight unit (kg/g), and light/dark switches. These settings are kept per browser session.

## Project layout

```text
manage.py                      Django command-line entry point
erp_web/                       Project settings and the root URL configuration
erp/                           The web app
  screens.py                   Screen list, menu layout and the permissions for each screen
  models.py                    Personal scenarios (Django database)
  bridge.py                    Opens the business SQLite database for each request
  dashboard.py                 Dashboard figures
  urls.py                      Screen URLs
  views/
    page.py                    Shared request handling: permissions, labels, messages, review state
    dashboard.py               Dashboard screen
    inventory.py               Warehouses: stock, catalog editor, count, ERP import
    purchasing.py              Purchase order list and management, receiving, and MRP
    stock.py                   Stock summary and reconciliation check
    records.py                 Projects, alternative SKUs and shipments
    scenarios.py               Personal what-if scenarios
    batches.py                 Batches and traceability
    planning.py                Product trees, production planning and the weekly plan
    readiness.py               PRR (production and packaging)
    arrivals.py                Dates of open purchase orders, for the week windows and PRR markers
    operations.py              Quick command, change log, undo, and settings switches
  templates/erp/               One template per screen, plus small shared parts (_planning_tabs, _arrivals, _icon_*)
  static/erp/app.css           Stylesheet (light and dark themes)
  static/erp/tables.js         Table tools shared by every list table
  static/erp/cell-popover.js   The floating week window
  templatetags/erp_icons.py    Icons and small template filters
  management/commands/         load_sample_data: loads the four sample formulas
cosmetics_erp/                 Business logic, shared with the tests (no web framework)
  config/                      Labels, translations and app constants
  db/                          SQLite schema, demo-data initialization, record tables and sample formulas
  services/                    Inventory/FEFO, planning, manufacturing, MRP, BOM rules, costing,
                               capacity, ERP import, backups, change review, where-used, readiness,
                               master-work simulations, personal scenarios, quick-command parsing
  text_language.py             Shows two-language item names in the page language
  formatting.py                Number, unit, and date formatting
tests/                         Service tests (pytest)
```

## How inventory and planning work

- Catalog item types are `RAW` (raw material), `BULK` (prepared formula), `PKG` (packaging) and `FG` (finished packaged product).
- Weight is stored in grams; packaging and finished goods are stored in units. The UI can display weight in grams or kilograms. Purchase-order weights are always entered in grams.
- BOM rows give the component quantities needed for one unit of the parent. For a bulk, weight components are grams per kg of bulk.
- Planning covers eight weekly periods (`W1`–`W8`). The dates come from the plan start date stored in the database. The PRR shows each week's start date and marks the current week.
- FEFO means **First Expired, First Out**. Production and packaging consume active batches in expiry order and skip expired batches by default. Several batches of the same material can be used in one run.
- For production and packaging, the output batch expiry is capped at the earliest expiry among the consumed component batches when that date is earlier.
- Receiving a PO or recording a manual receipt creates or updates a batch and adjusts catalog stock.
- A stock backup includes catalog, batches, batch consumption, stock movements, purchase orders, and product trees. A schedule backup includes the weekly schedule.
- Every backup and every undo is also written to the change log.
- Production and packaging runs are posted by `services/manufacturing.py`. The UI only collects inputs and shows messages.
- The readiness rule for PRR: green when the stock on hand covers the need, yellow when a purchase order arrives in time, red when it is short even with every arrival.
- Every purchase order that is not `Received` or `Cancelled` counts as an arrival, including `Draft` orders. An order dated before the plan start is counted in `W1`; an order after `W8` is not counted.

## Reading the PRR board

| Cell | Meaning |
| --- | --- |
| Quiet tile with a green line | Production uses the item that week and the stock on hand covers it. |
| Yellow tile | Covered only because a purchase order arrives. |
| Red tile with **!** | Short even with every arrival. |
| Dashed tile, grey number | No production uses the item that week; the stock is shown. |
| Blue truck | An order arrives that week. |
| Red truck | That week's order is past its date and not received. |
| Dashed truck | That week's arrival is only a draft order. |

## Data model

The SQLite schema is created by [`cosmetics_erp/db/schema.py`](./cosmetics_erp/db/schema.py). Its main tables are:

- `Catalog` — SKUs, item types, balances, suppliers, pricing, SAP code and warehouse metadata.
- `BOM` — parent/component relationships and per-product component requirements.
- `WeeklySchedule` — planned quantities for `W1` through `W8`.
- `PurchaseOrders` — quantities, suppliers, dates, destination warehouses and statuses.
- `Batches` — batch quantities, source, status and expiry.
- `StockMovements` — warehouse movement history.
- `BatchConsumption` — links consumed batches to the resulting batch for traceability.
- `Projects`, `AltSkus`, `Shipments` — the record tables behind the projects, alternative SKU and shipment screens.
- `TableBackups` — snapshots used by the undo controls.
- `AuditLog` — the change log.
- `Settings` — small key/value settings, such as the plan start date and the demo-data marker.

Django's own database (`django.sqlite3`) holds users, groups, sessions and the `Scenario` table.

## Demo data

A new business database starts with sample data: a face cream and a hair serum (each with a bulk formula, packaging and a finished product), hair-colour raw materials, two purchase orders, opening batches, a weekly plan, projects, alternative SKUs and shipments. All of it is invented.

### Four sample formulas

For a fuller demonstration, load the second set of sample data (also invented):

```powershell
python manage.py load_sample_data
```

- Four bulk formulas of 1,000 kg: jojoba hair wax, hyaluronic shampoo, hyaluronic hair mask and hand cream.
- A finished product for each pack size, with its own tree: wax 100 ml, shampoo 500 ml and 1 L, mask 500 ml and 1 L, hand cream 100 ml.
- Invented stock, suppliers and prices, an eight-week plan starting in the current week, and purchase orders that are late, due today, upcoming, draft, received and cancelled.

**This replaces the catalog, product trees, plan, purchase orders, projects, alternative SKUs and shipments.** The command asks you to type `yes` (or pass `--yes`) and first saves a copy of the database next to it, ending in `.bak`. Hair-colour items are kept. Personal simulator scenarios are not changed, so any that point to old products need to be edited. The data is defined in [`cosmetics_erp/db/sample_formulas.py`](./cosmetics_erp/db/sample_formulas.py).

The database files are not stored in git, so changes you make in the app stay on that computer. To move them, copy the database file (stop the app first).

## ERP import and assumptions to confirm

- **ERP import** reads CSV or Excel exports. The default column guesses use common SAP names (`MATNR`, `LABST`, `CHARG`, `VFDAT`, `EBELN`, `EINDT`, `LIFNR`) and Priority-style names (`PARTNAME`, `BALANCE`, `LOTNAME`, `EXPIRYDATE`, `ORDNAME`, `DUEDATE`). Confirm them against a real export. The app has no live SAP or Priority connection.
- Stock and PO quantities for weight items (RAW and BULK) are read in kg by default. The import screen lets you switch to grams.
- Catalog prices: RAW and BULK `item_price` is per kg. PKG and FG `item_price` is per unit. FG `item_price` is the selling price. Profit figures depend on these assumptions.

## Testing

```bash
python -m pip install pytest
python -m pytest                 # service tests
python manage.py test erp        # web app: screens, permissions, and each save flow
```

The tests use temporary databases and do not touch `cosmetics_3sim_erp.db`.

## Current scope

- No hosted database and no live SAP or Priority connection yet. SAP codes are catalog fields only.
- Projects, alternative SKUs and shipments show demo data; they are not yet connected to the real order flow.
- Comments on PRR rows and the PRR priority report are not built.
- The quick command is rule-based and does not call any external AI service.
- Treat the seeded data as demonstration data and take database backups before using real operational records.

## Hosting on PythonAnywhere

Replace `YOUR_USERNAME` everywhere below with your PythonAnywhere username.

1. **Open a Bash console** (Consoles tab) and get the code from the `main` branch:
   ```bash
   git clone -b main https://github.com/Bappito/Cosmetics-Project.git
   mkdir -p ~/erp-data
   mkvirtualenv --python=python3.12 erp
   pip install -r Cosmetics-Project/requirements.txt
   cd Cosmetics-Project
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   ```
2. **Create the secrets file** `~/erp_secrets.env` (the console has `nano`). Generate the key with `python -c "import secrets; print(secrets.token_urlsafe(50))"` and put it in:
   ```text
   DJANGO_SECRET_KEY=paste-the-generated-key
   DJANGO_DEBUG=0
   DJANGO_ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
   CSRF_TRUSTED_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com
   ERP_DB_PATH=/home/YOUR_USERNAME/erp-data/cosmetics_3sim_erp.db
   ```
3. **Create the web app** (Web tab > Add a new web app > Manual configuration > Python 3.12):
   - **Source code:** `/home/YOUR_USERNAME/Cosmetics-Project`
   - **Working directory:** `/home/YOUR_USERNAME/Cosmetics-Project`
   - **Virtualenv:** `/home/YOUR_USERNAME/.virtualenvs/erp`
   - **WSGI configuration file:** replace its contents with [`pythonanywhere/wsgi.py`](./pythonanywhere/wsgi.py) and set `USERNAME`.
   - **Static files:** URL `/static/`, directory `/home/YOUR_USERNAME/Cosmetics-Project/staticfiles`.
4. Press **Reload** on the Web tab and open `https://YOUR_USERNAME.pythonanywhere.com/`.

Notes:
- The business data is in `~/erp-data/cosmetics_3sim_erp.db`, and users are in `django.sqlite3` inside the project folder. Both stay when you reload or update the code.
- To update the app: in the console run `cd Cosmetics-Project && git pull && python manage.py migrate && python manage.py collectstatic --noinput`, then press **Reload**.
- The free plan needs a manual **Reload** about every three months, and it has CPU limits. Check the current limits on pythonanywhere.com.
- Create your own admin password with `createsuperuser`. Do not use a simple password on a public address.

## Database notes

The database runs in WAL mode with a busy timeout, so a few users can read while one writes. Stock changes that do not come from production or packaging, such as physical counts and reconciliations, are logged as `ADJUST` movements and consumption.
