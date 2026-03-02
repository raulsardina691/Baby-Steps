# Baby-Steps (Stage 1)

Stage 1 delivers a basic admin/data-foundation application for MRP setup.

## What this app includes

- SQLite database
- Admin UI to manage:
  - Items (including `safety_stock_qty`, `reorder_point_qty`)
  - Suppliers and supplier addresses
  - UOMs and UOM conversions
  - BOMs and BOM lines
  - Supplier items (MOQ, case size, cost)
  - Locations (seeded: MAIN_WAREHOUSE, 3PL, MOTOVOTANO, WHOLE_HERB)
- CSV import from `_inputs/`
- Data Audit report

## What is intentionally not included yet

- Inventory ledger
- MRP planning/netting logic

## Setup and run (non-developer friendly)

1. Install Python 3.10+ on your machine.
2. Open a terminal in this folder.
3. Run:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Start the app:

   ```bash
   python app.py
   ```

5. Open your browser to:

   `http://localhost:5000`

## First-time usage

1. Click **Initialize/Seed Database** on the dashboard.
2. Click **CSV Import** to load data from `_inputs/`.
3. Review and edit data via admin pages.
4. Open **Data Audit** to spot missing/incomplete records.

## Files

- `app.py` — Flask app and SQLite schema/routes
- `templates/` — HTML admin UI
- `static/` — CSS/JS
- `docs/mrp_input_schema_proposal.md` — Stage 1 schema proposal
- `_inputs/` — input CSV source files
