from __future__ import annotations

import sqlite3
from pathlib import Path

from .generator import OntologyGenerator
from .models import Ontology


CUSTOMERS = [
    ("CUST-001", "Arif Ramadhan", "arif@example.com", "Gold", "2024-03-15", 1245.50),
    ("CUST-002", "Jaroslav Cerny", "jaroslav@example.com", "Platinum", "2023-01-20", 3420.00),
    ("CUST-003", "Sumber Agvaan", "sumber@example.com", "Bronze", "2025-11-01", 89.00),
    ("CUST-004", "Mei Chen", "mei@example.com", "Gold", "2023-08-12", 2180.40),
    ("CUST-005", "Noah Patel", "noah@example.com", "Silver", "2024-06-01", 640.20),
    ("CUST-006", "Elena Rossi", "elena@example.com", "Platinum", "2022-11-09", 4105.75),
]

PRODUCTS = [
    ("PROD-001", "Ethiopian Single Origin", "Brewed", 4.50, "Ethiopia", 1, "SUPP-001"),
    ("PROD-002", "Colombian Latte", "Espresso", 5.75, "Colombia", 0, "SUPP-002"),
    ("PROD-003", "Nebula Cold Brew", "Cold Brew", 5.25, "Guatemala", 1, "SUPP-003"),
    ("PROD-004", "Kenya AA Pour Over", "Brewed", 6.10, "Kenya", 1, "SUPP-004"),
    ("PROD-005", "Almond Croissant", "Food", 4.25, "France", 0, "SUPP-002"),
    ("PROD-006", "House Espresso Capsule", "Merchandise", 12.00, "Brazil", 0, "SUPP-001"),
]

STORES = [
    ("STORE-001", "Fourth Coffee - Downtown Seattle", "Seattle", "WA", "2022-06-15", 45),
    ("STORE-002", "Fourth Coffee - Capitol Hill", "Seattle", "WA", "2023-02-28", 32),
    ("STORE-003", "Fourth Coffee - Bellevue", "Bellevue", "WA", "2024-04-10", 50),
]

SUPPLIERS = [
    ("SUPP-001", "Ethiopia Highlands Farm", "Ethiopia", "Fair Trade", 4.8),
    ("SUPP-002", "Colombian Mountain Roasters", "Colombia", "Rainforest Alliance", 4.6),
    ("SUPP-003", "Antigua Volcanic Co-op", "Guatemala", "Organic", 4.9),
    ("SUPP-004", "Nyeri Highlands Estate", "Kenya", "Direct Trade", 4.4),
]

ORDERS = [
    ("ORD-2025-001", "2025-01-28T09:15:00", 12.50, "Completed", "Mobile", "CUST-001", "STORE-001"),
    ("ORD-2025-002", "2025-01-28T10:30:00", 8.75, "Completed", "Card", "CUST-003", "STORE-002"),
    ("ORD-2025-003", "2025-02-02T08:05:00", 48.20, "Completed", "Mobile", "CUST-002", "STORE-001"),
    ("ORD-2025-004", "2025-02-03T14:22:00", 22.00, "Completed", "Gift Card", "CUST-004", "STORE-003"),
    ("ORD-2025-005", "2025-02-04T11:11:00", 67.40, "Completed", "Card", "CUST-006", "STORE-001"),
    ("ORD-2025-006", "2025-02-05T16:40:00", 15.30, "Preparing", "Cash", "CUST-005", "STORE-002"),
    ("ORD-2025-007", "2025-02-06T09:00:00", 91.10, "Completed", "Mobile", "CUST-006", "STORE-003"),
    ("ORD-2025-008", "2025-02-07T13:18:00", 33.80, "Completed", "Card", "CUST-002", "STORE-002"),
]

ORDER_LINES = [
    ("ORD-2025-001", "PROD-001", 2, 9.00),
    ("ORD-2025-001", "PROD-002", 1, 5.75),
    ("ORD-2025-002", "PROD-003", 1, 5.25),
    ("ORD-2025-003", "PROD-004", 4, 24.40),
    ("ORD-2025-003", "PROD-006", 2, 24.00),
    ("ORD-2025-004", "PROD-002", 2, 11.50),
    ("ORD-2025-004", "PROD-005", 2, 8.50),
    ("ORD-2025-005", "PROD-006", 3, 36.00),
    ("ORD-2025-005", "PROD-001", 4, 18.00),
    ("ORD-2025-006", "PROD-003", 2, 10.50),
    ("ORD-2025-007", "PROD-004", 6, 36.60),
    ("ORD-2025-007", "PROD-006", 3, 36.00),
    ("ORD-2025-008", "PROD-002", 3, 17.25),
    ("ORD-2025-008", "PROD-003", 2, 10.50),
]

SHIPMENTS = [
    ("SHIP-001", "2025-01-20", "2025-01-27", "Delivered", 250.5, "SUPP-001", "STORE-001"),
    ("SHIP-002", "2025-01-22", "2025-01-29", "Delivered", 180.0, "SUPP-002", "STORE-002"),
    ("SHIP-003", "2025-02-01", "2025-02-08", "In Transit", 320.0, "SUPP-003", "STORE-001"),
    ("SHIP-004", "2025-02-03", "2025-02-10", "Delivered", 410.0, "SUPP-001", "STORE-003"),
    ("SHIP-005", "2025-02-04", None, "Delayed", 95.0, "SUPP-004", "STORE-002"),
]

SHIP_LINES = [
    ("SHIP-001", "PROD-001", 120),
    ("SHIP-001", "PROD-006", 40),
    ("SHIP-002", "PROD-002", 80),
    ("SHIP-002", "PROD-005", 50),
    ("SHIP-003", "PROD-003", 200),
    ("SHIP-004", "PROD-001", 150),
    ("SHIP-004", "PROD-006", 90),
    ("SHIP-005", "PROD-004", 60),
]


def seed_database(ontology: Ontology, db_path: str | Path) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA busy_timeout = 8000")
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (name,) in tables:
            conn.execute(f'DROP TABLE IF EXISTS "{name.replace(chr(34), chr(34)*2)}"')
        conn.commit()
        for stmt in OntologyGenerator(ontology).ddl():
            conn.executescript(stmt)
        conn.executemany(
            "INSERT INTO customer (customer_id, name, email, loyalty_tier, join_date, total_spend) VALUES (?,?,?,?,?,?)",
            CUSTOMERS,
        )
        conn.executemany(
            "INSERT INTO product (product_id, name, category, price, origin, is_organic, supplier_id) VALUES (?,?,?,?,?,?,?)",
            PRODUCTS,
        )
        conn.executemany(
            "INSERT INTO store (store_id, name, city, state, open_date, capacity) VALUES (?,?,?,?,?,?)",
            STORES,
        )
        conn.executemany(
            "INSERT INTO supplier (supplier_id, name, country, certification, rating) VALUES (?,?,?,?,?)",
            SUPPLIERS,
        )
        conn.executemany(
            "INSERT INTO \"order\" (order_id, timestamp, total, status, payment_method, customer_id, store_id) VALUES (?,?,?,?,?,?,?)",
            ORDERS,
        )
        conn.executemany(
            "INSERT INTO order_contains_product (order_id, product_id, quantity, line_amount) VALUES (?,?,?,?)",
            ORDER_LINES,
        )
        conn.executemany(
            "INSERT INTO shipment (shipment_id, dispatch_date, arrival_date, status, weight, supplier_id, store_id) VALUES (?,?,?,?,?,?,?)",
            SHIPMENTS,
        )
        conn.executemany(
            "INSERT INTO shipment_contains_product (shipment_id, product_id, quantity) VALUES (?,?,?)",
            SHIP_LINES,
        )
        conn.commit()
    finally:
        conn.close()
    return path
