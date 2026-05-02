from pathlib import Path
import sqlite3

from src.config import get_required_instance_paths


SEED_INSTANCE_IDS = ("APP_DEV", "APP_TEST")


SCHEMA = """
DROP TABLE IF EXISTS sales_order_lines;
DROP TABLE IF EXISTS sales_orders;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS facilities;
DROP TABLE IF EXISTS items;

CREATE TABLE items (
    item_id TEXT PRIMARY KEY,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_of_measure TEXT NOT NULL
);

CREATE TABLE facilities (
    facility_id TEXT PRIMARY KEY,
    facility_name TEXT NOT NULL,
    region TEXT NOT NULL
);

CREATE TABLE inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    on_hand_quantity REAL NOT NULL,
    reserved_quantity REAL NOT NULL,
    reorder_point REAL NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE sales_orders (
    sales_order_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    order_date TEXT NOT NULL,
    requested_ship_date TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE sales_order_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_order_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    ordered_quantity REAL NOT NULL,
    shipped_quantity REAL NOT NULL
);
"""


def seed_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)

        conn.executemany(
            "INSERT INTO items VALUES (?, ?, ?, ?)",
            [
                ("ITEM-1001", "Steel Coil", "Raw Material", "TON"),
                ("ITEM-1002", "Bolt Pack", "Hardware", "EA"),
                ("ITEM-1003", "Paint Drum", "Chemicals", "EA"),
            ],
        )

        conn.executemany(
            "INSERT INTO facilities VALUES (?, ?, ?)",
            [
                ("FAC-UT", "Utah Warehouse", "West"),
                ("FAC-OH", "Ohio Plant", "Midwest"),
            ],
        )

        conn.executemany(
            """
            INSERT INTO inventory
            (item_id, facility_id, on_hand_quantity, reserved_quantity, reorder_point, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("ITEM-1001", "FAC-UT", 20, 8, 50, "2026-04-30"),
                ("ITEM-1002", "FAC-UT", 500, 120, 200, "2026-04-30"),
                ("ITEM-1003", "FAC-OH", 12, 4, 25, "2026-04-30"),
            ],
        )

        conn.executemany(
            "INSERT INTO sales_orders VALUES (?, ?, ?, ?, ?)",
            [
                ("SO-1001", "Acme", "2026-04-20", "2026-05-05", "OPEN"),
                ("SO-1002", "Globex", "2026-04-22", "2026-05-08", "BACKORDERED"),
            ],
        )

        conn.executemany(
            """
            INSERT INTO sales_order_lines
            (sales_order_id, item_id, facility_id, ordered_quantity, shipped_quantity)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("SO-1001", "ITEM-1001", "FAC-UT", 40, 10),
                ("SO-1002", "ITEM-1003", "FAC-OH", 20, 0),
            ],
        )


def main() -> None:
    for db_path in get_required_instance_paths(SEED_INSTANCE_IDS):
        seed_database(db_path)
        print(f"Created {db_path}")


if __name__ == "__main__":
    main()
