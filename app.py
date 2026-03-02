import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "stage1.db"
INPUTS_DIR = BASE_DIR / "_inputs"

app = Flask(__name__)
app.secret_key = "stage1-dev-key"


CSV_IMPORTS = {
    "items": "Codex Info - Tea Map.csv",
    "suppliers": "Codex Info - Supplier Contact Info.csv",
    "bom_lines": "Codex Info - BOMs Exploded.csv",
    "supplier_items_whc": "Codex Info - BOM Whole Herb Company.csv",
    "supplier_items_motovotano": "Codex Info - BOM Motovotano.csv",
    "case_sizes": "Codex Info - Case Sizes.csv",
    "costs": "Codex Info - Cost.csv",
}

LOCATION_SEEDS = ["MAIN_WAREHOUSE", "3PL", "MOTOVOTANO", "WHOLE_HERB"]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            uom_code TEXT,
            safety_stock_qty REAL DEFAULT 0,
            reorder_point_qty REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS supplier_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            line1 TEXT NOT NULL,
            line2 TEXT,
            city TEXT,
            state TEXT,
            postal_code TEXT,
            country TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS uoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS uom_conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_uom_code TEXT NOT NULL,
            to_uom_code TEXT NOT NULL,
            multiplier REAL NOT NULL,
            UNIQUE(from_uom_code, to_uom_code)
        );

        CREATE TABLE IF NOT EXISTS boms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_item_id INTEGER NOT NULL,
            revision TEXT,
            effective_date TEXT,
            notes TEXT,
            FOREIGN KEY (parent_item_id) REFERENCES items(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bom_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bom_id INTEGER NOT NULL,
            component_item_id INTEGER NOT NULL,
            qty_per REAL NOT NULL,
            uom_code TEXT,
            FOREIGN KEY (bom_id) REFERENCES boms(id) ON DELETE CASCADE,
            FOREIGN KEY (component_item_id) REFERENCES items(id)
        );

        CREATE TABLE IF NOT EXISTS supplier_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            supplier_sku TEXT,
            moq REAL DEFAULT 0,
            case_size REAL DEFAULT 0,
            cost REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            UNIQUE(supplier_id, item_id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            rows_imported INTEGER DEFAULT 0,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        );
        """
    )

    for code in LOCATION_SEEDS:
        db.execute(
            "INSERT OR IGNORE INTO locations (code, name) VALUES (?, ?)",
            (code, code.replace("_", " ").title()),
        )

    db.commit()


def table_rows(query: str, params=()):
    return get_db().execute(query, params).fetchall()


def upsert_item(sku: str, name: str, uom_code: str = ""):
    db = get_db()
    db.execute(
        """
        INSERT INTO items (sku, name, uom_code)
        VALUES (?, ?, ?)
        ON CONFLICT(sku) DO UPDATE SET
            name = excluded.name,
            uom_code = COALESCE(excluded.uom_code, items.uom_code)
        """,
        (sku.strip(), name.strip() or sku.strip(), uom_code.strip() or None),
    )


def fetch_item_id_by_sku(sku: str):
    row = get_db().execute("SELECT id FROM items WHERE sku = ?", (sku,)).fetchone()
    return row["id"] if row else None


def import_csv_data():
    db = get_db()
    totals = {}

    tea_map = INPUTS_DIR / CSV_IMPORTS["items"]
    if tea_map.exists():
        count = 0
        with tea_map.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sku = (
                    row.get("Internal SKU")
                    or row.get("SKU")
                    or row.get("Product SKU")
                    or ""
                ).strip()
                name = (
                    row.get("Name")
                    or row.get("Product Name")
                    or row.get("Tea Name")
                    or sku
                )
                if not sku:
                    continue
                upsert_item(sku, name)
                count += 1
        totals[tea_map.name] = count

    supplier_file = INPUTS_DIR / CSV_IMPORTS["suppliers"]
    if supplier_file.exists():
        count = 0
        with supplier_file.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = (row.get("Supplier") or row.get("Supplier Name") or "").strip()
                if not name:
                    continue
                code = (row.get("Code") or name.upper().replace(" ", "_")[:20]).strip()
                db.execute(
                    """
                    INSERT INTO suppliers (code, name, email, phone, notes)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(code) DO UPDATE SET
                        name=excluded.name,
                        email=excluded.email,
                        phone=excluded.phone,
                        notes=excluded.notes
                    """,
                    (
                        code,
                        name,
                        row.get("Email", ""),
                        row.get("Phone", ""),
                        row.get("Notes", ""),
                    ),
                )
                supplier_id = db.execute(
                    "SELECT id FROM suppliers WHERE code = ?", (code,)
                ).fetchone()["id"]
                line1 = row.get("Address") or row.get("Line 1") or ""
                if line1.strip():
                    db.execute(
                        """
                        INSERT INTO supplier_addresses (supplier_id, line1, line2, city, state, postal_code, country)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            supplier_id,
                            line1,
                            row.get("Line 2", ""),
                            row.get("City", ""),
                            row.get("State", ""),
                            row.get("Postal", ""),
                            row.get("Country", ""),
                        ),
                    )
                count += 1
        totals[supplier_file.name] = count

    bom_file = INPUTS_DIR / CSV_IMPORTS["bom_lines"]
    if bom_file.exists():
        count = 0
        with bom_file.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                parent_sku = (row.get("Parent SKU") or row.get("Parent") or "").strip()
                component_sku = (row.get("Component SKU") or row.get("Component") or "").strip()
                qty = float((row.get("Qty") or row.get("Quantity") or "0") or 0)
                if not parent_sku or not component_sku:
                    continue
                upsert_item(parent_sku, parent_sku)
                upsert_item(component_sku, component_sku)
                parent_id = fetch_item_id_by_sku(parent_sku)
                component_id = fetch_item_id_by_sku(component_sku)
                bom_row = db.execute(
                    "SELECT id FROM boms WHERE parent_item_id = ?", (parent_id,)
                ).fetchone()
                if bom_row:
                    bom_id = bom_row["id"]
                else:
                    db.execute(
                        "INSERT INTO boms (parent_item_id, revision, effective_date) VALUES (?, ?, ?)",
                        (parent_id, "A", datetime.utcnow().date().isoformat()),
                    )
                    bom_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                exists = db.execute(
                    "SELECT id FROM bom_lines WHERE bom_id = ? AND component_item_id = ?",
                    (bom_id, component_id),
                ).fetchone()
                if exists:
                    db.execute(
                        "UPDATE bom_lines SET qty_per = ?, uom_code = ? WHERE id = ?",
                        (qty, row.get("UOM", ""), exists["id"]),
                    )
                else:
                    db.execute(
                        "INSERT INTO bom_lines (bom_id, component_item_id, qty_per, uom_code) VALUES (?, ?, ?, ?)",
                        (bom_id, component_id, qty, row.get("UOM", "")),
                    )
                count += 1
        totals[bom_file.name] = count

    for supplier_key, supplier_name in [
        ("supplier_items_whc", "WHOLE_HERB"),
        ("supplier_items_motovotano", "MOTOVOTANO"),
    ]:
        csv_file = INPUTS_DIR / CSV_IMPORTS[supplier_key]
        if not csv_file.exists():
            continue

        sup = db.execute(
            "SELECT id FROM suppliers WHERE code = ?",
            (supplier_name,),
        ).fetchone()
        if not sup:
            db.execute(
                "INSERT INTO suppliers (code, name) VALUES (?, ?)",
                (supplier_name, supplier_name.replace("_", " ").title()),
            )
            sup = db.execute(
                "SELECT id FROM suppliers WHERE code = ?",
                (supplier_name,),
            ).fetchone()

        count = 0
        with csv_file.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sku = (row.get("Component SKU") or row.get("SKU") or "").strip()
                if not sku:
                    continue
                upsert_item(sku, row.get("Component Name") or sku)
                item_id = fetch_item_id_by_sku(sku)
                moq = float((row.get("MOQ") or "0") or 0)
                case_size = float((row.get("Case Size") or "0") or 0)
                db.execute(
                    """
                    INSERT INTO supplier_items (supplier_id, item_id, supplier_sku, moq, case_size, cost)
                    VALUES (?, ?, ?, ?, ?, COALESCE((SELECT cost FROM supplier_items WHERE supplier_id=? AND item_id=?), 0))
                    ON CONFLICT(supplier_id, item_id) DO UPDATE SET
                        supplier_sku=excluded.supplier_sku,
                        moq=excluded.moq,
                        case_size=excluded.case_size
                    """,
                    (sup["id"], item_id, row.get("Supplier SKU", sku), moq, case_size, sup["id"], item_id),
                )
                count += 1
        totals[csv_file.name] = count

    db.execute("DELETE FROM import_log")
    for source_name, rows_imported in totals.items():
        db.execute(
            "INSERT INTO import_log (source_name, rows_imported, notes) VALUES (?, ?, ?)",
            (source_name, rows_imported, "Stage 1 CSV import"),
        )

    db.commit()
    return totals


@app.route("/")
def index():
    stats = {
        "items": table_rows("SELECT COUNT(*) AS c FROM items")[0]["c"],
        "suppliers": table_rows("SELECT COUNT(*) AS c FROM suppliers")[0]["c"],
        "boms": table_rows("SELECT COUNT(*) AS c FROM boms")[0]["c"],
        "bom_lines": table_rows("SELECT COUNT(*) AS c FROM bom_lines")[0]["c"],
        "supplier_items": table_rows("SELECT COUNT(*) AS c FROM supplier_items")[0]["c"],
        "locations": table_rows("SELECT COUNT(*) AS c FROM locations")[0]["c"],
    }
    return render_template("dashboard.html", stats=stats)


@app.route("/seed")
def seed_data():
    init_db()
    flash("Database schema initialized and locations seeded.", "success")
    return redirect(url_for("index"))


@app.route("/import")
def run_import():
    init_db()
    totals = import_csv_data()
    flash(f"CSV import completed for {len(totals)} files.", "success")
    return render_template("import_result.html", totals=totals)


@app.route("/audit")
def audit_report():
    issues = []
    db = get_db()

    missing_supplier_addresses = db.execute(
        """
        SELECT s.name FROM suppliers s
        LEFT JOIN supplier_addresses a ON a.supplier_id = s.id
        WHERE a.id IS NULL
        """
    ).fetchall()
    if missing_supplier_addresses:
        issues.append(("Suppliers missing addresses", [r["name"] for r in missing_supplier_addresses]))

    missing_item_uom = db.execute(
        "SELECT sku FROM items WHERE uom_code IS NULL OR uom_code = ''"
    ).fetchall()
    if missing_item_uom:
        issues.append(("Items missing base UOM", [r["sku"] for r in missing_item_uom][:25]))

    orphan_bom_lines = db.execute(
        """
        SELECT bl.id FROM bom_lines bl
        LEFT JOIN boms b ON b.id = bl.bom_id
        LEFT JOIN items i ON i.id = bl.component_item_id
        WHERE b.id IS NULL OR i.id IS NULL
        """
    ).fetchall()
    if orphan_bom_lines:
        issues.append(("Orphan BOM lines", [str(r["id"]) for r in orphan_bom_lines]))

    return render_template("audit.html", issues=issues)


@app.route("/items", methods=["GET", "POST"])
def items():
    init_db()
    db = get_db()
    if request.method == "POST":
        db.execute(
            """
            INSERT INTO items (sku, name, uom_code, safety_stock_qty, reorder_point_qty)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request.form["sku"],
                request.form["name"],
                request.form.get("uom_code", ""),
                float(request.form.get("safety_stock_qty", 0) or 0),
                float(request.form.get("reorder_point_qty", 0) or 0),
            ),
        )
        db.commit()
        flash("Item added", "success")
        return redirect(url_for("items"))

    rows = table_rows("SELECT * FROM items ORDER BY id DESC")
    return render_template("items.html", rows=rows)


@app.route("/suppliers", methods=["GET", "POST"])
def suppliers():
    init_db()
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO suppliers (code, name, email, phone, notes) VALUES (?, ?, ?, ?, ?)",
            (
                request.form["code"],
                request.form["name"],
                request.form.get("email", ""),
                request.form.get("phone", ""),
                request.form.get("notes", ""),
            ),
        )
        supplier_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.execute(
            """
            INSERT INTO supplier_addresses (supplier_id, line1, line2, city, state, postal_code, country)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                supplier_id,
                request.form.get("line1", ""),
                request.form.get("line2", ""),
                request.form.get("city", ""),
                request.form.get("state", ""),
                request.form.get("postal_code", ""),
                request.form.get("country", ""),
            ),
        )
        db.commit()
        flash("Supplier added", "success")
        return redirect(url_for("suppliers"))

    rows = table_rows(
        """
        SELECT s.*, a.line1, a.city, a.state
        FROM suppliers s
        LEFT JOIN supplier_addresses a ON a.supplier_id = s.id
        ORDER BY s.id DESC
        """
    )
    return render_template("suppliers.html", rows=rows)


@app.route("/uoms", methods=["GET", "POST"])
def uoms():
    init_db()
    db = get_db()
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "uom":
            db.execute(
                "INSERT OR IGNORE INTO uoms (code, description) VALUES (?, ?)",
                (request.form["code"], request.form.get("description", "")),
            )
        elif form_type == "conversion":
            db.execute(
                """
                INSERT INTO uom_conversions (from_uom_code, to_uom_code, multiplier)
                VALUES (?, ?, ?)
                ON CONFLICT(from_uom_code, to_uom_code) DO UPDATE SET
                    multiplier=excluded.multiplier
                """,
                (
                    request.form["from_uom_code"],
                    request.form["to_uom_code"],
                    float(request.form.get("multiplier", 1)),
                ),
            )
        db.commit()
        flash("UOM data saved", "success")
        return redirect(url_for("uoms"))

    return render_template(
        "uoms.html",
        uoms=table_rows("SELECT * FROM uoms ORDER BY code"),
        conversions=table_rows("SELECT * FROM uom_conversions ORDER BY from_uom_code, to_uom_code"),
    )


@app.route("/boms", methods=["GET", "POST"])
def boms():
    init_db()
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO boms (parent_item_id, revision, effective_date, notes) VALUES (?, ?, ?, ?)",
            (
                int(request.form["parent_item_id"]),
                request.form.get("revision", "A"),
                request.form.get("effective_date", ""),
                request.form.get("notes", ""),
            ),
        )
        db.commit()
        flash("BOM created", "success")
        return redirect(url_for("boms"))

    return render_template(
        "boms.html",
        boms=table_rows(
            "SELECT b.*, i.sku AS parent_sku FROM boms b JOIN items i ON i.id = b.parent_item_id ORDER BY b.id DESC"
        ),
        items=table_rows("SELECT id, sku FROM items ORDER BY sku"),
    )


@app.route("/bom-lines", methods=["GET", "POST"])
def bom_lines():
    init_db()
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO bom_lines (bom_id, component_item_id, qty_per, uom_code) VALUES (?, ?, ?, ?)",
            (
                int(request.form["bom_id"]),
                int(request.form["component_item_id"]),
                float(request.form.get("qty_per", 0) or 0),
                request.form.get("uom_code", ""),
            ),
        )
        db.commit()
        flash("BOM line created", "success")
        return redirect(url_for("bom_lines"))

    return render_template(
        "bom_lines.html",
        rows=table_rows(
            """
            SELECT bl.*, b.parent_item_id, p.sku AS parent_sku, c.sku AS component_sku
            FROM bom_lines bl
            JOIN boms b ON b.id = bl.bom_id
            JOIN items p ON p.id = b.parent_item_id
            JOIN items c ON c.id = bl.component_item_id
            ORDER BY bl.id DESC
            """
        ),
        boms=table_rows(
            "SELECT b.id, i.sku FROM boms b JOIN items i ON i.id = b.parent_item_id ORDER BY i.sku"
        ),
        items=table_rows("SELECT id, sku FROM items ORDER BY sku"),
    )


@app.route("/supplier-items", methods=["GET", "POST"])
def supplier_items():
    init_db()
    db = get_db()
    if request.method == "POST":
        db.execute(
            """
            INSERT INTO supplier_items (supplier_id, item_id, supplier_sku, moq, case_size, cost, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(supplier_id, item_id) DO UPDATE SET
                supplier_sku=excluded.supplier_sku,
                moq=excluded.moq,
                case_size=excluded.case_size,
                cost=excluded.cost,
                currency=excluded.currency
            """,
            (
                int(request.form["supplier_id"]),
                int(request.form["item_id"]),
                request.form.get("supplier_sku", ""),
                float(request.form.get("moq", 0) or 0),
                float(request.form.get("case_size", 0) or 0),
                float(request.form.get("cost", 0) or 0),
                request.form.get("currency", "USD"),
            ),
        )
        db.commit()
        flash("Supplier item saved", "success")
        return redirect(url_for("supplier_items"))

    return render_template(
        "supplier_items.html",
        rows=table_rows(
            """
            SELECT si.*, s.name AS supplier_name, i.sku AS item_sku
            FROM supplier_items si
            JOIN suppliers s ON s.id = si.supplier_id
            JOIN items i ON i.id = si.item_id
            ORDER BY si.id DESC
            """
        ),
        suppliers=table_rows("SELECT id, name FROM suppliers ORDER BY name"),
        items=table_rows("SELECT id, sku FROM items ORDER BY sku"),
    )


@app.route("/locations", methods=["GET", "POST"])
def locations():
    init_db()
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT OR IGNORE INTO locations (code, name) VALUES (?, ?)",
            (request.form["code"], request.form["name"]),
        )
        db.commit()
        flash("Location added", "success")
        return redirect(url_for("locations"))

    return render_template("locations.html", rows=table_rows("SELECT * FROM locations ORDER BY code"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
