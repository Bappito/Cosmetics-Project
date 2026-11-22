# Cosmetics ERP - https://cosmetics-project.streamlit.app

A Streamlit application for managing a small cosmetics manufacturing workflow. It brings inventory, purchasing, production planning, packaging, batches, and basic traceability together in one dashboard backed by a local SQLite database.

The interface supports Hebrew (right-to-left) and English (left-to-right), and includes a compact dashboard style with custom CSS.

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

- Python 3.10 or newer
- Packages listed in [`requirements.txt`](./requirements.txt)

## Run locally

```bash
git clone https://github.com/Bappito/Cosmetics-Project.git
cd Cosmetics-Project

python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints the local URL when the server starts (usually <http://localhost:8501>).

Run the command from the repository root. The application creates or opens `cosmetics_3sim_erp.db` in the current working directory. On first initialization, it creates the schema and inserts demo catalog, BOM, schedule, purchase-order, and opening-batch data if the catalog is empty. Later changes are persisted in that SQLite file.

## Main screens

| Screen | What it is for |
| --- | --- |
| Dashboard | Opening page: stock totals, expiry and PO counts, what can be packed now, and estimated profit per finished product. |
| Warehouses | Stock, expiry dates, purchase orders, suppliers, stock movements, and catalog editing for raw materials, bulk, and packaging. Also **Update by Count** (physical count) and **ERP Import** (SAP / Priority CSV or Excel exports). |
| Production Line Simulator | Plan bulk production and check raw-material availability; report production to consume raw-material batches and add a bulk batch. |
| Packaging Simulator | Plan finished-product packaging and check bulk and packaging availability; report packaging to create a finished-goods batch. |
| Master Work Simulator | Review finished-product plans across the eight-week schedule and see projected availability and shortages. |
| Purchase Orders | Maintain PO rows and statuses, view arrival weeks, and receive orders into a warehouse. |
| Batches & Traceability | Review batch balances and expiry, add manual receipts, and inspect batch consumption links. |
| Quick Command Agent | Add stock using a simple text command. |

## How inventory and planning work

- Catalog item types are `RAW` (raw material), `BULK` (prepared formula), `PKG` (packaging), and `FG` (finished packaged product).
- Weight is stored in grams; packaging and finished goods are stored in units. The UI can display weight in grams or kilograms.
- BOM rows define the component quantities needed for bulk or finished products.
- Planning covers eight weekly periods (`W1`–`W8`). Dates and labels are currently defined in the configuration code.
- FEFO means **First Expired, First Out**. Production and packaging consume active batches in expiry order and exclude expired batches by default.
- For production and packaging, the output batch expiry is capped at the earliest expiry among the consumed component batches when that date is earlier than the requested output expiry.
- Receiving a PO or recording a manual receipt creates or updates a batch and adjusts catalog stock.
- A stock backup includes catalog, batches, batch consumption, stock movements, and purchase orders. A schedule backup includes the weekly schedule.

## Project layout

```text
app.py                         Streamlit startup, shared dependency wiring, and page dispatch
cosmetics_erp/
  config/                      UI labels, translations, and app constants
  db/                          SQLite connection and schema/demo-data initialization
  services/                    Inventory/FEFO, planning, and backup operations
  ui/
    components.py              Shared planning, shortage, and undo UI
    context.py                 Dependencies passed to page renderers
    formatting.py              Shared number and unit formatting
    navigation.py              Sidebar, language, and session-state behavior
    styles.py                  Loads and injects the stylesheet
    pages/                     One Streamlit renderer per application screen
static/
  css/app.css                  Custom dashboard styles
  js/                          Reserved for custom JavaScript; currently empty
requirements.txt               Python package dependencies
```

Screen-specific database queries currently live with their corresponding page renderers. Shared inventory, planning, and backup behavior is kept in the service modules.

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

## Current scope

This repository contains a local Streamlit app and SQLite storage. It does not include authentication, a hosted database, or live SAP connectivity; SAP codes are catalog fields only. The quick-command screen is rule-based and does not call any external AI service. Treat the seeded data as demonstration data and take appropriate database backups before using real operational records.

## Access control

Set a password before hosting the app. The app checks it on the first screen.

- Streamlit Cloud: add `APP_PASSWORD = "..."` in the app's secrets.
- Local or server: set the environment variable `COSMETICS_APP_PASSWORD`.

If neither is set, the app opens without a password. Use that only on a single machine.

## ERP import and assumptions to confirm

- **ERP Import** reads CSV or Excel exports. The default column guesses use common SAP names (`MATNR`, `LABST`, `CHARG`, `VFDAT`, `EBELN`, `EINDT`, `LIFNR`) and Priority-style names (`PARTNAME`, `BALANCE`, `LOTNAME`, `EXPIRYDATE`, `ORDNAME`, `DUEDATE`). Confirm them against a real export. The app has no live SAP or Priority connection.
- Stock and PO quantities for weight items (RAW and BULK) are read in kg by default. The import screen lets you switch to grams.
- Catalog prices: RAW and BULK `item_price` is per kg. PKG and FG `item_price` is per unit. FG `item_price` is treated as the selling price. Profit figures depend on these assumptions.

## Testing

```powershell
python -m pip install pytest
python -m pytest
```

The tests use an in-memory database and do not touch `cosmetics_3sim_erp.db`.

## Database notes

The database runs in WAL mode with a busy timeout, so a few users can read while one writes. Stock changes that do not come from production or packaging, such as physical counts and reconciliations, are logged as `ADJUST` movements and consumption.
