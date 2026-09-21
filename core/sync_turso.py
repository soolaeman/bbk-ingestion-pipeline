"""
Syncs new/updated products from local SQLite (bbk.db) to Turso Edge DB.
"""

import os
import sys
import sqlite3
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ai_gateway import load_env

load_env()
sys.stdout.reconfigure(line_buffering=True)

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "Jarvis-OS",
    "domains",
    "business",
    "bbkitchen",
    "data",
    "bbk.db"
)

import argparse

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "libsql://bbk-soolaeman.aws-ap-northeast-1.turso.io")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

def get_turso_endpoint():
    return TURSO_URL.replace("libsql://", "https://").rstrip("/") + "/v2/pipeline"

def get_headers():
    return {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json"
    }

def sync_master_tables():
    http_url = get_turso_endpoint()
    headers = get_headers()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=== Syncing Master Tables (Categories & Warehouses) to Turso ===")
    
    # 1. Master Categories
    cat_rows = cur.execute("SELECT * FROM master_categories").fetchall()
    create_cat_sql = """
    CREATE TABLE IF NOT EXISTS master_categories (
        term_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        parent_id INTEGER NOT NULL,
        parent_slug TEXT,
        description TEXT,
        thumbnail TEXT
    )"""
    upsert_cat_sql = """
    INSERT INTO master_categories (term_id, name, slug, parent_id, parent_slug, description, thumbnail)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(term_id) DO UPDATE SET
        name=excluded.name,
        slug=excluded.slug,
        parent_id=excluded.parent_id,
        parent_slug=excluded.parent_slug,
        description=excluded.description,
        thumbnail=excluded.thumbnail
    """
    
    # 2. Master Warehouses
    wh_rows = cur.execute("SELECT * FROM master_warehouses").fetchall()
    create_wh_sql = """
    CREATE TABLE IF NOT EXISTS master_warehouses (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        hub_id TEXT NOT NULL,
        location TEXT NOT NULL,
        telegram_id TEXT
    )"""
    upsert_wh_sql = """
    INSERT INTO master_warehouses (code, name, hub_id, location, telegram_id)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(code) DO UPDATE SET
        name=excluded.name,
        hub_id=excluded.hub_id,
        location=excluded.location,
        telegram_id=excluded.telegram_id
    """

    stmts = [{"sql": create_cat_sql, "args": []}, {"sql": create_wh_sql, "args": []}]
    
    for r in cat_rows:
        args = [
            {"type": "integer", "value": str(r["term_id"])},
            {"type": "text", "value": str(r["name"])},
            {"type": "text", "value": str(r["slug"])},
            {"type": "integer", "value": str(r["parent_id"])},
            {"type": "text", "value": str(r["parent_slug"] or "")},
            {"type": "text", "value": str(r["description"] or "")},
            {"type": "text", "value": str(r["thumbnail"] or "")}
        ]
        stmts.append({"sql": upsert_cat_sql, "args": args})

    for r in wh_rows:
        args = [
            {"type": "text", "value": str(r["code"])},
            {"type": "text", "value": str(r["name"])},
            {"type": "text", "value": str(r["hub_id"])},
            {"type": "text", "value": str(r["location"])},
            {"type": "text", "value": str(r["telegram_id"] or "")}
        ]
        stmts.append({"sql": upsert_wh_sql, "args": args})

    payload = {
        "requests": [{"type": "execute", "stmt": s} for s in stmts] + [{"type": "close"}]
    }
    res = requests.post(http_url, headers=headers, json=payload, timeout=30)
    if res.status_code == 200:
        print(f"  Master tables synced OK ({len(cat_rows)} categories, {len(wh_rows)} warehouses).")
    else:
        print(f"  [ERROR] Master tables sync failed ({res.status_code}): {res.text[:250]}")
    conn.close()

def sync_to_turso(min_sku=None, only_dirty=False, batch_size=25):
    http_url = get_turso_endpoint()
    headers = get_headers()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if only_dirty:
        query = "SELECT * FROM products WHERE is_dirty = 1 ORDER BY CAST(SUBSTR(sku, 4) AS INTEGER) ASC"
        rows = cur.execute(query).fetchall()
        print(f"=== Syncing {len(rows)} DIRTY products to Turso Edge DB ===")
    elif min_sku:
        query = "SELECT * FROM products WHERE sku >= ? ORDER BY CAST(SUBSTR(sku, 4) AS INTEGER) ASC"
        rows = cur.execute(query, (min_sku,)).fetchall()
        print(f"=== Syncing {len(rows)} products to Turso Edge DB (min_sku={min_sku}) ===")
    else:
        query = "SELECT * FROM products ORDER BY CAST(SUBSTR(sku, 4) AS INTEGER) ASC"
        rows = cur.execute(query).fetchall()
        print(f"=== Syncing ALL {len(rows)} products to Turso Edge DB ===")

    total = len(rows)
    if total == 0:
        print("No products to sync.")
        conn.close()
        return

    cols = rows[0].keys()
    col_names = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    update_clause = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "sku"])
    upsert_sql = f"INSERT INTO products ({col_names}) VALUES ({placeholders}) ON CONFLICT(sku) DO UPDATE SET {update_clause}"

    synced = 0
    synced_skus = []
    for i in range(0, total, batch_size):
        batch = rows[i:i+batch_size]
        stmts = []
        for r in batch:
            args = []
            for col in cols:
                val = r[col]
                if val is None:
                    args.append({"type": "null"})
                elif isinstance(val, int):
                    args.append({"type": "integer", "value": str(val)})
                elif isinstance(val, float):
                    args.append({"type": "float", "value": val})
                else:
                    args.append({"type": "text", "value": str(val)})
            stmts.append({"sql": upsert_sql, "args": args})

        payload = {
            "requests": [{"type": "execute", "stmt": s} for s in stmts] + [{"type": "close"}]
        }
        res = requests.post(http_url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            synced += len(batch)
            synced_skus.extend([r["sku"] for r in batch])
            print(f"  Synced batch [{synced}/{total}] to Turso OK")
        else:
            print(f"  [ERROR] Turso batch failed ({res.status_code}): {res.text[:200]}")

    # Reset is_dirty for synced items
    if synced_skus:
        placeholders_clean = ", ".join(["?"] * len(synced_skus))
        cur.execute(f"UPDATE products SET is_dirty = 0 WHERE sku IN ({placeholders_clean})", synced_skus)
        conn.commit()

    print(f"Turso Sync Finished: {synced}/{total} products synced. is_dirty reset OK.")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync products and master tables to Turso Edge DB")
    parser.add_argument("--dirty", action="store_true", help="Sync only products marked with is_dirty=1")
    parser.add_argument("--master", action="store_true", help="Sync master_categories and master_warehouses")
    parser.add_argument("--min-sku", type=str, default=None, help="Sync products starting from specific SKU")
    parser.add_argument("--all", action="store_true", help="Sync all products")
    args = parser.parse_args()

    if args.master or (not args.dirty and not args.min_sku and not args.all):
        sync_master_tables()

    if args.dirty:
        sync_to_turso(only_dirty=True)
    elif args.all:
        sync_to_turso()
    elif args.min_sku:
        sync_to_turso(min_sku=args.min_sku)
    else:
        # Default behavior: sync dirty items if any, otherwise sync min_sku BBK2798
        conn = sqlite3.connect(DB_PATH)
        dirty_count = conn.execute("SELECT count(*) FROM products WHERE is_dirty = 1").fetchone()[0]
        conn.close()
        if dirty_count > 0:
            sync_to_turso(only_dirty=True)
        else:
            sync_to_turso(min_sku="BBK2798")
