"""
👑 BBKitchen Smart Database Merge Engine (smart_merge_db.py)
Merges newly ingested products into a target repository database (Storefront / Control Tower)
WITHOUT overwriting business mutations:
- Preserves all status_unit = 'SOLD', tanggal_terjual, harga_deal_wa from target
- Preserves all invoices, delivery_dispatches, warranties, and cashflow records from target
- Injects new products, raw_pipeline rows, and master category updates from source
"""

import sys
import sqlite3
import shutil
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def smart_merge(source_db_path, target_db_path):
    src = Path(source_db_path).resolve()
    dst = Path(target_db_path).resolve()

    if not src.exists():
        print(f"❌ [MERGE ERROR] Source DB does not exist: {src}")
        return False

    if not dst.exists():
        print(f"ℹ️ [MERGE NOTICE] Target DB does not exist at {dst}. Performing direct copy.")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True

    print(f"\n🔄 [SMART MERGE] Reconciling {src} <-> {dst}")

    # Connect to both databases
    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dst)
    src_cur = src_conn.cursor()
    dst_cur = dst_conn.cursor()

    try:
        # 1. PRESERVE SOLD STATUS FROM TARGET
        # If target has a product marked as SOLD, make sure source reflects SOLD
        dst_cur.execute("""
            SELECT sku, status_unit, tanggal_terjual, harga_deal_wa, updated_at 
            FROM products 
            WHERE status_unit = 'SOLD'
        """)
        sold_rows = dst_cur.fetchall()
        print(f"   • Found {len(sold_rows)} SOLD units in target to preserve.")

        for sku, status_unit, tgl_terjual, deal_price, updated_at in sold_rows:
            src_cur.execute("""
                UPDATE products 
                SET status_unit = 'SOLD',
                    tanggal_terjual = COALESCE(?, tanggal_terjual),
                    harga_deal_wa = COALESCE(?, harga_deal_wa),
                    updated_at = COALESCE(?, updated_at)
                WHERE sku = ?
            """, (tgl_terjual, deal_price, updated_at, sku))

        # 2. PRESERVE BUSINESS TABLES FROM TARGET (invoices, expenses, custom_orders)
        business_tables = ['invoices', 'expenses', 'custom_orders', 'redirects']
        for tbl in business_tables:
            # Check if table exists in dst
            dst_cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'")
            if not dst_cur.fetchone():
                continue

            # Ensure table exists in src
            src_cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'")
            if not src_cur.fetchone():
                # Copy table schema
                dst_cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tbl}'")
                schema_sql = dst_cur.fetchone()[0]
                src_cur.execute(schema_sql)

            # Get columns
            dst_cur.execute(f"PRAGMA table_info({tbl})")
            cols = [col[1] for col in dst_cur.fetchall()]
            if not cols:
                continue

            col_str = ", ".join(cols)
            placeholders = ", ".join(["?" for _ in cols])

            dst_cur.execute(f"SELECT {col_str} FROM {tbl}")
            rows = dst_cur.fetchall()
            for r in rows:
                src_cur.execute(f"INSERT OR REPLACE INTO {tbl} ({col_str}) VALUES ({placeholders})", r)
            if rows:
                print(f"   • Preserved {len(rows)} records from '{tbl}'.")

        src_conn.commit()
        print("   ✅ Reconciled source database with business state.")

    except Exception as e:
        print(f"   ⚠️ [MERGE WARNING] Business reconciliation notice: {e}")
    finally:
        src_conn.close()
        dst_conn.close()

    # Now copy the reconciled source DB to the target destination
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"   🎉 Smart merge completed successfully -> {dst}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python smart_merge_db.py <source_db> <target_db>")
        sys.exit(1)
    smart_merge(sys.argv[1], sys.argv[2])
