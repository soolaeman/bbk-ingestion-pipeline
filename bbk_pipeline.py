"""
BBKitchen Sovereign Ingestion Pipeline CLI
Unified operational entrypoint for:
- fetch: Pull raw messages & photos from partner Telegram channels
- normalize: AI & regex normalization, categories & warehouses SSOT mapping
- sync: Sync clean catalog & master tables to Turso Edge DB
- run-all: Complete end-to-end automated daily pipeline run
"""

import sys
import os
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from ai_gateway import load_env
load_env()

def main():
    parser = argparse.ArgumentParser(
        description="BBKitchen Sovereign Ingestion Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bbk_pipeline.py normalize --limit 10   # Test normalize 10 pending items
  python bbk_pipeline.py sync --dirty           # Sync modified items to Turso Edge
  python bbk_pipeline.py sync --master          # Sync categories & warehouses SSOT
  python bbk_pipeline.py run-all                # Execute fetch -> normalize -> sync
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Pipeline operation mode")

    # Command: fetch
    parser_fetch = subparsers.add_parser("fetch", help="Fetch raw messages from Telegram partner channels")
    parser_fetch.add_argument("--limit", type=int, default=50, help="Maximum messages to fetch per channel")

    # Command: normalize
    parser_norm = subparsers.add_parser("normalize", help="Process raw items with AI & SSOT taxonomy")
    parser_norm.add_argument("--limit", type=int, default=None, help="Limit number of raw records to process")
    parser_norm.add_argument("--dry-run", action="store_true", help="Dry run without writing to SQLite")

    # Command: sync
    parser_sync = subparsers.add_parser("sync", help="Sync SQLite products & master tables to Turso Edge")
    parser_sync.add_argument("--dirty", action="store_true", help="Sync only dirty (updated/new) records")
    parser_sync.add_argument("--master", action="store_true", help="Sync master categories & warehouses")
    parser_sync.add_argument("--all", action="store_true", help="Sync all products")
    parser_sync.add_argument("--min-sku", type=str, default=None, help="Sync products from minimum SKU")

    # Command: run-all
    parser_all = subparsers.add_parser("run-all", help="Execute complete automated pipeline (fetch -> normalize -> sync)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "fetch":
        print("=== [STEP 1/3] Fetching from Telegram Channels ===")
        try:
            from telethon_fetch import fetch_telegram_messages
            fetch_telegram_messages(limit=args.limit)
        except ImportError:
            print("[INFO] telethon_fetch module not found or requires active Telethon session. Checking autonomous_telegram_sync...")
            try:
                import subprocess
                subprocess.run(["python", os.path.join(os.path.dirname(__file__), "autonomous_telegram_sync.py")], check=True)
            except Exception as e:
                print(f"[ERROR] Fetch execution failed: {e}")

    elif args.command == "normalize":
        print("=== [STEP 2/3] Normalizing Raw Pipeline with SSOT ===")
        from process_raw_pipeline import run_pipeline
        run_pipeline(dry_run=args.dry_run, limit=args.limit)

    elif args.command == "sync":
        print("=== [STEP 3/3] Syncing to Turso Cloud Edge ===")
        from sync_turso import sync_to_turso, sync_master_tables
        if args.master or (not args.dirty and not args.all and not args.min_sku):
            sync_master_tables()
        if args.dirty:
            sync_to_turso(only_dirty=True)
        elif args.all:
            sync_to_turso()
        elif args.min_sku:
            sync_to_turso(min_sku=args.min_sku)
        else:
            sync_to_turso(only_dirty=True)

    elif args.command == "run-all":
        print("==================================================")
        print("👑 BBKitchen Sovereign Automated Pipeline Execution")
        print("==================================================")
        
        # 1. Fetch
        print("\n--- 1. Fetching Telegram Messages ---")
        try:
            import subprocess
            subprocess.run(["python", os.path.join(os.path.dirname(__file__), "autonomous_telegram_sync.py")], check=False)
        except Exception as e:
            print(f"[WARN] Fetch step skipped or encountered warning: {e}")

        # 2. Normalize
        print("\n--- 2. Normalizing Catalog with AI & SSOT ---")
        from process_raw_pipeline import run_pipeline
        run_pipeline(dry_run=False)

        # 3. Sync
        print("\n--- 3. Syncing to Turso Cloud Edge ---")
        from sync_turso import sync_to_turso, sync_master_tables
        sync_master_tables()
        sync_to_turso(only_dirty=True)

        print("\n✅ Sovereign Pipeline Run Complete.")

if __name__ == "__main__":
    main()
