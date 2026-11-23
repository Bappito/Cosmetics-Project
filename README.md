# Cosmetics ERP

A web app for managing a small cosmetics manufacturing workflow. It brings inventory, purchasing, production planning, packaging, batches, and basic traceability together in one place, backed by a local SQLite database.

The interface supports Hebrew (right-to-left) and English (left-to-right). Users sign in, and what they can see and change depends on their role. The app is built with Django.

## Features

- **Inventory and warehouses** — view raw materials, bulk formulas, and packaging stock; check batch expiry, open purchase orders, suppliers, recent stock movements, and catalog items.
- **Eight-week planning** — plan production by parent SKU and week, review projected component use and shortages, and account for incoming purchase orders.
- **Production simulation** — calculate raw-material needs from the bill of materials (BOM), consume eligible component batches using FEFO, and create bulk batches.
- **Packaging simulation** — consume bulk material and packaging components, then create finished-product batches.
- **Purchase orders** — edit orders, review their ETA in the planning window, and receive an order into inventory with a supplier batch number and expiry date.
- **Batch tracking** — view active and depleted batches, monitor expiry, receive stock manually, and trace component consumption backward or forward.
- **Backups and undo** — save snapshots before supported changes and restore the latest stock or schedule snapshot. The application keeps up to 20 backups per scope.
- **Quick command** — enter a simple stock-addition command such as `תוסיף 5 קילו ל-1001` or `תוסיף 300 יחידות ל-3001`. This is a local command parser; the current implementation does not call an external AI service.
- **Bilingual controls** — switch Hebrew/English and choose grams or kilograms for weight displays.


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

Then open http://127.0.0.1:8000/ and sign in with the superuser account.

The app uses two SQLite files:

- `cosmetics_3sim_erp.db` — the business data (catalog, batches, purchase orders, planning). It is created and filled with demo data on first use. The Streamlit version used this same file, so existing data carries over.
- `django.sqlite3` — users, groups, and sessions.

Settings can be changed with environment variables:

- `DJANGO_SECRET_KEY`: required before hosting.
- `DJANGO_DEBUG`: set to `0` when hosting.
- `DJANGO_ALLOWED_HOSTS`: comma-separated host names, for example `erp.example.com`.
- `ERP_DB_PATH`: the business database file. Defaults to `cosmetics_3sim_erp.db` in the repository folder.

## Users and roles

Assign roles in the admin at http://127.0.0.1:8000/admin/ under **Groups**. Every screen has a view and an edit permission.

- **Admin:** every screen, including profit.
- **Warehouse:** the dashboard, inventory and purchase orders.
- **Viewer:** the dashboard only, without profit.

Anyone who is not signed in is sent to the login page. The screens a user cannot view are hidden from the sidebar, and direct links to them return "403 Forbidden".

## Screens

| Screen | URL | What it is for |
| --- | --- | --- |
| Dashboard | `/` | Opening page: expiry and PO counts, what can be packed now, the estimated profit per finished product, and the plan start date. |
| Warehouses | `/inventory/` | Stock, expiry dates, purchase orders, suppliers, catalog editing, **Update by count**, and **ERP import** (SAP / Priority CSV or Excel exports). |
| Purchase orders | `/purchase-orders/` | Edit PO rows and statuses, view arrival weeks, and receive an order into a warehouse. |
| Purchase planning (MRP) | `/mrp/` | Works out what to buy from the eight-week plan. Suggestions are rounded to MOQ and can become draft POs. The Excel download has the weekly detail. |
| Batches & traceability | `/batches/` | Batch balances and expiry, manual receipts, and batch consumption links. |
| Product trees (BOM) | `/bom/` | Add or edit the components of a bulk or finished product. Invalid combinations are blocked before saving. |
| 1. Production simulator | `/production/` | Plan bulk production and check raw-material availability; report production to consume raw-material batches and add a bulk batch. |
| 2. Packaging simulator | `/packaging/` | Plan finished-product packaging and check bulk and packaging availability; report packaging to create a finished-goods batch. |
| 3. Master work simulator | `/master-work/` | Review finished-product plans across the eight-week schedule and see projected availability and shortages. |
| Quick command agent | `/quick-command/` | Add stock using a simple text command. |
| Change log | `/audit/` | Every stock, product-tree and planning change, including undos, with its time. |

Each change goes through the same steps: check it, review the preview, tick the confirmation, and save. A backup is taken before each save so the last change can be undone.

The sidebar also has language (Hebrew/English), weight unit (kg/g), and light/dark switches. These settings are kept per browser session.

## Project layout

```text
manage.py                      Django command-line entry point
erp_web/                       Project settings and the root URL configuration
erp/                           The web app
  screens.py                   Screen list and the permissions that control each screen
  bridge.py                    Opens the business SQLite database for each request
  dashboard.py                 Dashboard figures
  urls.py                      Screen URLs
  views/
    page.py                    Shared request handling: permissions, labels, messages, review state
    dashboard.py               Dashboard screen
    inventory.py               Warehouses: stock, catalog editor, count, ERP import
    purchasing.py              Purchase orders, receiving, and MRP
    batches.py                 Batches and traceability
    planning.py                Product trees, simulators, weekly plan, master work
    operations.py              Quick command, change log, undo, and settings switches
  templates/erp/               One template per screen
  static/erp/app.css           Stylesheet (light and dark themes)
cosmetics_erp/                 Business logic, shared with the tests (no web framework)
  config/                      Labels, translations, and app constants
  db/                          SQLite schema and demo-data initialization
  services/                    Inventory/FEFO, planning, manufacturing, MRP, BOM rules, costing,
                               capacity, ERP import, backups, change review, where-used and
                               master-work simulations, quick-command parsing
  formatting.py                Number, unit, and date formatting
tests/                         Service tests (pytest)
```

Screen-specific code lives in the view modules. Shared inventory, planning, and backup behavior is kept in the service modules, so it can be tested without the web layer.

## How inventory and planning work

- Catalog item types are `RAW` (raw material), `BULK` (prepared formula), `PKG` (packaging), and `FG` (finished packaged product).
- Weight is stored in grams; packaging and finished goods are stored in units. The UI can display weight in grams or kilograms.
- BOM rows define the component quantities needed for bulk or finished products.
- Planning covers eight weekly periods (`W1`–`W8`). The start date is stored in the database and does not move on its own. Change it on the dashboard; the weekly quantities stay as they are and are attached to the new weeks.
- FEFO means **First Expired, First Out**. Production and packaging consume active batches in expiry order and exclude expired batches by default.
- For production and packaging, the output batch expiry is capped at the earliest expiry among the consumed component batches when that date is earlier than the requested output expiry.
- Receiving a PO or recording a manual receipt creates or updates a batch and adjusts catalog stock.
- A stock backup includes catalog, batches, batch consumption, stock movements, purchase orders, and product trees. A schedule backup includes the weekly schedule.
- Every backup and every undo is also written to the change log, which is never trimmed.
- Production and packaging runs are posted by `services/manufacturing.py`. The UI only collects inputs and shows messages.


## Data model

The SQLite schema is initialized by [`cosmetics_erp/db/schema.py`](./cosmetics_erp/db/schema.py). Its main tables are:

- `Catalog` — SKUs, item types, balances, suppliers, pricing, and warehouse metadata.
- `BOM` — parent/component relationships and per-product component requirements.
- `WeeklySchedule` — planned quantities for `W1` through `W8`.
- `PurchaseOrders` — quantities, suppliers, dates, destination warehouses, and statuses.
- `Batches` — batch quantities, source, status, and expiry.
- `StockMovements` — warehouse movement history.
- `BatchConsumption` — links batches consumed to the resulting parent batch for traceability.
- `TableBackups` — snapshots used by the undo controls.
- `AuditLog` — the change log: time, area, and action for every backup and undo.
- `Settings` — small key/value settings, such as the plan start date.


## ERP import and assumptions to confirm

- **ERP Import** reads CSV or Excel exports. The default column guesses use common SAP names (`MATNR`, `LABST`, `CHARG`, `VFDAT`, `EBELN`, `EINDT`, `LIFNR`) and Priority-style names (`PARTNAME`, `BALANCE`, `LOTNAME`, `EXPIRYDATE`, `ORDNAME`, `DUEDATE`). Confirm them against a real export. The app has no live SAP or Priority connection.
- Stock and PO quantities for weight items (RAW and BULK) are read in kg by default. The import screen lets you switch to grams.
- Catalog prices: RAW and BULK `item_price` is per kg. PKG and FG `item_price` is per unit. FG `item_price` is treated as the selling price. Profit figures depend on these assumptions.


## Testing

```bash
python -m pip install pytest
python -m pytest                 # service tests
python manage.py test erp        # web app: screens, permissions, and each save flow
```

The tests use temporary databases and do not touch `cosmetics_3sim_erp.db`.

## Current scope

This repository contains a Django web app with SQLite storage. It does not include a hosted database or live SAP connectivity; SAP codes are catalog fields only. The quick-command screen is rule-based and does not call any external AI service. Treat the seeded data as demonstration data and take appropriate database backups before using real operational records.

Set a secret key and allowed hosts before hosting the app, and turn debug off:

```bash
DJANGO_SECRET_KEY=... DJANGO_DEBUG=0 DJANGO_ALLOWED_HOSTS=erp.example.com python manage.py runserver 0.0.0.0:8000
```

Use a production WSGI server (for example gunicorn behind a reverse proxy with HTTPS) for real use.

## Database notes

The database runs in WAL mode with a busy timeout, so a few users can read while one writes. Stock changes that do not come from production or packaging, such as physical counts and reconciliations, are logged as `ADJUST` movements and consumption.

