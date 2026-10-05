"""
👑 BBKitchen Sovereign SQLite Repository Synchronizer (sync_repos.py)
Synchronizes SQLite SSOT by replicating the master bbk.db 
across all local repos (bbk-storefront, bbk-control-tower, Jarvis-OS).
Guarantees zero-network-latency embedded SQLite operation.
"""

import os
import sys
import shutil
import sqlite3
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def get_master_db():
    current_dir = Path(__file__).resolve().parent
    candidates = [
        current_dir.parent / "bbk.db",
        current_dir.parent / "data" / "bbk.db",
        current_dir.parent.parent / "Jarvis-OS" / "domains" / "business" / "bbkitchen" / "data" / "bbk.db",
    ]
    best_cand = None
    best_sku = -1
    for cand in candidates:
        if cand.exists() and cand.stat().st_size > 100_000:
            try:
                conn = sqlite3.connect(cand)
                cur = conn.cursor()
                cur.execute("SELECT MAX(CAST(SUBSTR(sku, 4) AS INTEGER)) FROM products WHERE sku LIKE 'BBK%'")
                row = cur.fetchone()
                val = row[0] if row and row[0] is not None else 0
                conn.close()
                if val > best_sku:
                    best_sku = val
                    best_cand = cand
            except Exception:
                pass
    return best_cand

def sync_master_db(source_db=None):
    if not source_db:
        source_db = get_master_db()
    
    if not source_db or not os.path.exists(source_db):
        print("❌ [SYNC ERROR] Master database bbk.db not found!")
        return False
        
    src_path = Path(source_db).resolve()
    
    # Verify integrity
    try:
        conn = sqlite3.connect(src_path)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        status = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM products")
        total_products = cur.fetchone()[0]
        cur.execute("SELECT MAX(CAST(SUBSTR(sku, 4) AS INTEGER)) FROM products WHERE sku LIKE 'BBK%'")
        max_sku = cur.fetchone()[0]
        conn.close()
        
        if status.lower() != "ok":
            print(f"❌ [SYNC ERROR] Source DB integrity failed: {status}")
            return False
    except Exception as e:
        print(f"❌ [SYNC ERROR] DB verification failed: {e}")
        return False

    # Detect workspace root
    root_github = None
    for p in [src_path.parent, src_path.parent.parent, src_path.parent.parent.parent, src_path.parent.parent.parent.parent]:
        if (p / "bbk-storefront").exists() or (p / "bbk-ingestion-pipeline").exists():
            root_github = p
            break

    target_paths = []
    if root_github:
        target_paths = [
            root_github / "bbk-storefront" / "data" / "bbk.db",
            root_github / "bbk-control-tower" / "data" / "bbk.db",
            root_github / "bbk-ingestion-pipeline" / "bbk.db",
            root_github / "Jarvis-OS" / "domains" / "business" / "bbkitchen" / "data" / "bbk.db",
        ]
    else:
        pipeline_dir = Path(__file__).resolve().parent.parent
        target_paths = [
            pipeline_dir / "bbk.db",
            pipeline_dir.parent / "bbk-storefront" / "data" / "bbk.db",
            pipeline_dir.parent / "bbk-control-tower" / "data" / "bbk.db",
            pipeline_dir.parent / "Jarvis-OS" / "domains" / "business" / "bbkitchen" / "data" / "bbk.db",
        ]

    print("\n=======================================================")
    print("👑 BBKitchen Sovereign SQLite Repository Synchronizer")
    print("=======================================================")
    print(f"Source DB  : {src_path}")
    print(f"Size       : {src_path.stat().st_size:,} bytes")
    print(f"Catalog    : {total_products} products (Max SKU: BBK{max_sku})")
    print(f"Integrity  : {status.upper()} ✅")
    print("-------------------------------------------------------")

    synced_count = 0
    for target in target_paths:
        target_resolved = target.resolve()
        if target_resolved == src_path:
            continue
        
        # Only copy if parent repository/directory exists
        repo_dir = target_resolved.parent if target_resolved.parent.name != "data" else target_resolved.parent.parent
        if repo_dir.exists():
            target_resolved.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_path, target_resolved)
                print(f"✅ Synced -> {target_resolved} ({target_resolved.stat().st_size:,} bytes)")
                synced_count += 1
            except Exception as err:
                print(f"⚠️ Failed to copy to {target_resolved}: {err}")

    print(f"\n🎉 Successfully replicated bbk.db to {synced_count} repository targets.")
    return True

if __name__ == "__main__":
    sync_master_db()
