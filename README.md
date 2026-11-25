# Cosmetics ERP

A web app for a cosmetics manufacturing company. It brings stock, purchasing, production planning, packaging, batches, traceability, projects, shipments, readiness checks and personal what-if scenarios together in one place. The business data lives in a local SQLite database. The app is built with Streamlit.

The interface supports Hebrew (right-to-left) and English (left-to-right).

## Requirements

- Python 3.10 or newer
- Packages listed in [`requirements.txt`](./requirements.txt)

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints the local URL when the server starts (usually http://localhost:8501). Run the command from the repository root. The app creates or opens `cosmetics_3sim_erp.db` in that folder and fills it with demo data the first time.

## Sign-in and personal scenarios

At the first screen, enter a name and, when one is set, the password.

- Set a password before hosting: add `APP_PASSWORD = "..."` in the app's secrets on Streamlit Community Cloud, or set the environment variable `COSMETICS_APP_PASSWORD` when running locally. Without it, the app opens without a password.
- The name keeps each person's scenarios apart. It is not a secure account: anyone who knows the password can type another name.

## Features

- **Warehouses** — stock by warehouse, expiry dates, suppliers, catalog editing, physical count, and ERP import (SAP or Priority CSV/Excel exports). Each row shows its unit (kg, g or units).
- **Stock summary** — totals by warehouse and by item type, plus a check that compares catalog balances with the sum of their active batches.
- **Purchase orders** — two screens: **Purchase orders** (a read-only list of all orders, with search and a status filter) and **Purchase orders management** (edit, review, and receive an order into a warehouse).
- **Purchase planning (MRP)** — works out what to buy from the eight-week plan. Suggestions are rounded to the minimum order quantity and can become draft POs.
- **Product trees (BOM)** — a list of all parent products. Each product opens a tree page with its components, stock, ratio to the parent and how many parent units the stock covers. A bulk component opens to show its own raw materials.
- **Production planning** — one page with three tabs: production line, packaging, and master work. Each shows the weekly plan, component use per SKU (one row per component, with a total across all products that use it), and the cumulative balance.
- **PRR (project readiness)** — one screen with a switch between **Production** (bulk products and their raw materials) and **Packaging** (finished products and their bulk and packaging). It shows weekly readiness, the users of each component, supplier, open orders and alternatives.
- **Batches and traceability** — batch balances and expiry, manual receipts, and consumption links. Production and packaging use batches in FEFO order (earliest expiry first), so several batches of the same material can be used in one run.
- **My simulator** — a private what-if scenario for each user: planned orders by week, with the shortages they would cause. A scenario can be shared for viewing; shared scenarios are read-only for everyone else.
- **Projects, alternative SKUs and shipments** — read-only lists with demo data.
- **Change log, backups and undo** — every save is preceded by a backup, and every backup and undo is written to the change log.
- **Quick command** — add stock with a simple text command such as `תוסיף 5 קילו ל-1001`. This is a local parser; no external AI service is called.
- **Tables** — every table has a search box, a row count, click-to-sort headers, paging, and an export to Excel (CSV, which Excel opens with Hebrew text intact).
- **Language and units** — Hebrew/English. Item names that are written in two languages show only the current language. Weight can be shown in grams or kilograms.

## Project layout

```text
app.py                         Streamlit startup, shared dependency wiring, and page dispatch
cosmetics_erp/
  config/                      UI labels, translations, and app constants
  db/                          SQLite connection, schema, demo data, and records (projects, alternatives, shipments, scenarios)
  services/                    Inventory/FEFO, planning, manufacturing, MRP, BOM rules, costing,
                               capacity, ERP import, backups, change review, scenarios,
                               where-used and master-work simulations, quick-command parsing,
                               and readiness
  ui/
    auth.py                    Name and password sign-in
    components.py              Shared planning, shortage, and undo UI
    context.py                 Dependencies passed to page renderers
    formatting.py              Shared number and unit formatting
    navigation.py              Sidebar, language, and session-state behavior
    styles.py                  Loads and injects the stylesheet
    pages/                     One Streamlit renderer per application screen
static/
  css/app.css                  Custom stylesheet
tests/                         Service and app tests (pytest)
requirements.txt               Python package dependencies
```

Screen-specific database queries currently live with their corresponding page renderers. Shared inventory, planning, and backup behavior is kept in the service modules.

## How inventory and planning work

- Catalog item types are `RAW` (raw material), `BULK` (prepared formula), `PKG` (packaging) and `FG` (finished packaged product).
- Weight is stored in grams; packaging and finished goods are stored in units. The UI can display weight in grams or kilograms. Purchase-order weights are always entered in grams.
- BOM rows give the component quantities needed for one unit of the parent. For a bulk, weight components are grams per kg of bulk.
- Planning covers eight weekly periods (`W1`–`W8`). Week headers show only the week number; the dates come from the plan start date stored in the database.
- FEFO means **First Expired, First Out**. Production and packaging consume active batches in expiry order and skip expired batches by default. Several batches of the same material can be used in one run.
- For production and packaging, the output batch expiry is capped at the earliest expiry among the consumed component batches when that date is earlier.
- Receiving a PO or recording a manual receipt creates or updates a batch and adjusts catalog stock.
- A stock backup includes catalog, batches, batch consumption, stock movements, purchase orders, and product trees. A schedule backup includes the weekly schedule.
- Every backup and every undo is also written to the change log.
- Production and packaging runs are posted by `services/manufacturing.py`. The UI only collects inputs and shows messages.
- The readiness rule for PRR: green when the stock on hand covers the need, yellow when a purchase order arrives in time, red when it is short even with every arrival.


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

Projects, alternative SKUs, shipments, and personal scenarios are stored in the same SQLite file (tables `Projects`, `AltSkus`, `Shipments`, `Scenarios`).


## Demo data

The business database starts with demo data: four formulas of one ton each (keratin shampoo, hyaluronic shampoo, hyaluronic hair mask and hand cream), their raw materials, packaging, finished products, invented purchase orders, batches, a weekly plan and shipments. Once the owner replaces the demo data, the marker `demo_reset_done` in `Settings` stops the old sample rows from being loaded again.


## ERP import and assumptions to confirm

- **ERP import** reads CSV or Excel exports. The default column guesses use common SAP names (`MATNR`, `LABST`, `CHARG`, `VFDAT`, `EBELN`, `EINDT`, `LIFNR`) and Priority-style names (`PARTNAME`, `BALANCE`, `LOTNAME`, `EXPIRYDATE`, `ORDNAME`, `DUEDATE`). Confirm them against a real export. The app has no live SAP or Priority connection.
- Stock and PO quantities for weight items (RAW and BULK) are read in kg by default. The import screen lets you switch to grams.
- Catalog prices: RAW and BULK `item_price` is per kg. PKG and FG `item_price` is per unit. FG `item_price` is the selling price. Profit figures depend on these assumptions.


## Testing

```bash
python -m pip install pytest
python -m pytest
```

The tests use temporary databases and do not touch `cosmetics_3sim_erp.db`.

## Hosting

The app runs on Streamlit Community Cloud from this repository's `main` branch: point it at `app.py` and set `APP_PASSWORD` in the app's secrets. The community cloud stores files in the app's own storage, so the database may reset when the app restarts. Check that before relying on it for real records.

## Current scope

This repository contains a local Streamlit app and SQLite storage. It does not include a hosted database or live SAP connectivity; SAP codes are catalog fields only. The quick-command screen is rule-based and does not call any external AI service. Treat the seeded data as demonstration data and take appropriate database backups before using real operational records.

## Database notes

The database runs in WAL mode with a busy timeout, so a few users can read while one writes. Stock changes that do not come from production or packaging, such as physical counts and reconciliations, are logged as `ADJUST` movements and consumption.
