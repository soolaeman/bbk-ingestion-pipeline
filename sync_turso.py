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

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "libsql://bbk-soolaeman.aws-ap-northeast-1.turso.io")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

def sync_to_turso(min_sku="BBK2798", batch_size=25):
    http_url = TURSO_URL.replace("libsql://", "https://").rstrip("/") + "/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json"
    }

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = "SELECT * FROM products WHERE sku >= ? ORDER BY CAST(SUBSTR(sku, 4) AS INTEGER) ASC"
    rows = cur.execute(query, (min_sku,)).fetchall()
    total = len(rows)
    print(f"=== Syncing {total} products to Turso Edge DB (min_sku={min_sku}) ===")

    if total == 0:
        print("No products to sync.")
        return

    cols = rows[0].keys()
    col_names = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    update_clause = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "sku"])
    upsert_sql = f"INSERT INTO products ({col_names}) VALUES ({placeholders}) ON CONFLICT(sku) DO UPDATE SET {update_clause}"

    synced = 0
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
            print(f"  Synced batch [{synced}/{total}] to Turso OK")
        else:
            print(f"  [ERROR] Turso batch failed ({res.status_code}): {res.text[:200]}")

    print(f"Turso Sync Finished: {synced}/{total} products synced.")
    conn.close()

if __name__ == "__main__":
    sync_to_turso()
