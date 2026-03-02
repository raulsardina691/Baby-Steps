# MRP Input Schema Proposal (Stage 1)

This proposal captures the Stage 1 input and normalized schema used by the Baby-Steps app.
It intentionally excludes inventory ledger and MRP planning outputs.

## Core Entities

### items
- `sku` (unique)
- `name`
- `uom_code`
- `safety_stock_qty`
- `reorder_point_qty`

### suppliers
- `code` (unique)
- `name`
- `email`
- `phone`
- `notes`

### supplier_addresses
- linked by `supplier_id`
- `line1`, `line2`, `city`, `state`, `postal_code`, `country`

### uoms
- `code` (unique)
- `description`

### uom_conversions
- `from_uom_code`
- `to_uom_code`
- `multiplier`

### boms
- `parent_item_id`
- `revision`
- `effective_date`
- `notes`

### bom_lines
- `bom_id`
- `component_item_id`
- `qty_per`
- `uom_code`

### supplier_items
- `supplier_id`
- `item_id`
- `supplier_sku`
- `moq`
- `case_size`
- `cost`
- `currency`

### locations
Seeded values:
- `MAIN_WAREHOUSE`
- `3PL`
- `MOTOVOTANO`
- `WHOLE_HERB`

## Stage 1 Source Inputs

- `Codex Info - Tea Map.csv` → item seed data
- `Codex Info - Supplier Contact Info.csv` → suppliers and addresses
- `Codex Info - BOMs Exploded.csv` → boms and bom_lines
- `Codex Info - BOM Whole Herb Company.csv` → supplier_items (WHOLE_HERB)
- `Codex Info - BOM Motovotano.csv` → supplier_items (MOTOVOTANO)
- `Codex Info - Case Sizes.csv` → supplier packaging references
- `Codex Info - Cost.csv` → supplier cost references

## Data Audit Checks

The Stage 1 audit report flags:
1. Suppliers missing addresses.
2. Items missing base UOM.
3. Orphan BOM lines.

## Explicitly Out of Scope in Stage 1

- Inventory ledger
- MRP engine and planned order generation
