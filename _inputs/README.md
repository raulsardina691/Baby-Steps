# Inputs

This folder contains source data files (CSVs, exports, notes)
used by Codex to build the MRP / Inventory app.

Files will be added here progressively.
# Inputs

This folder contains source data files (CSVs, exports, notes)
used by Codex to build the MRP / Inventory / PO Calculator app.

These files are the **source of truth** and should be imported into
normalized database tables. No values should be hardcoded.

---

## File Index

### Codex Info - Motovotano Inventory.csv
- Supplier inventory on-hand at Motovotano
- Used for: supplier inventory, MRP netting, inbound availability

### Codex Info - Whole Herb Company Inventory.csv
- Supplier inventory on-hand at Whole Herb Company
- Used for: supplier inventory and PO netting

### Codex Info - Packaging Exploded.csv
- Exploded packaging components per finished product
- Used for: BOM explosion and PO calculations

### Codex Info - Supplier Contact Info.csv
- Supplier master data (contacts, terms, notes)
- Used for: supplier table and PO headers

### Codex Info - BOMs Exploded.csv
- Fully exploded BOMs
- Parent SKU → component SKU → quantity
- Used for: core MRP logic

### Codex Info - BOM Whole Herb Company.csv
- Supplier-specific BOM lines for Whole Herb Company
- Includes case size and sourcing rules
- Used for: supplier PO calculation

### Codex Info - BOM Motovotano.csv
- Supplier-specific BOM lines for Motovotano
- Includes case size and sourcing rules
- Used for: supplier PO calculation

### Codex Info - Tea Map.csv
- Maps finished goods to internal SKUs / names
- Used for: product master normalization

### Codex Info - Case Sizes.csv
- Case sizes and MOQs by supplier/component
- Used for: PO rounding and MOQ enforcement

### Codex Info - Cost.csv
- Cost data per component / packaging
- Used for: PO totals and inventory valuation

---

## Notes for Codex

- Centralize all UOM conversions (lb, oz, g, gal, ml)
- Supplier case sizes override generic BOM quantities
- Inventory ledger must be append-only
- All calculations must expose intermediate math steps
