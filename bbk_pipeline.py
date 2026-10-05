"""
BBKitchen Sovereign Ingestion Pipeline CLI
Unified operational entrypoint for:
- fetch: Pull raw messages & photos from partner Telegram channels
- normalize: AI & regex normalization, categories & warehouses SSOT mapping
- sync: Replicate master SQLite bbk.db across sovereign repositories
- run-all: Complete end-to-end automated daily pipeline run
"""

import sys
import os
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from ai_gateway import load_env
load_env()

def ensure_preflight_sync(no_sync=False):
    """
    🛡️ BBKitchen Anti-Collision Pre-Flight Sync Guard
    Checks if running locally and verifies upstream origin/main.
    If Cloud Bot has pushed new updates/commits, automatically pulls and replicates
    master bbk.db locally before any SKU calculation or processing begins.
    Guarantees zero split-brain collisions between Cloud and Local.
    """
    if no_sync:
        print("ℹ️ [PRE-FLIGHT GUARD] Upstream sync dilewati (--no-sync aktif).")
        return True

    if os.getenv("GITHUB_ACTIONS") == "true":
        print("🛡️ [PRE-FLIGHT GUARD] Berjalan di GitHub Actions (Cloud Runner SSOT).")
        return True

    repo_dir = Path(__file__).resolve().parent
    git_dir = repo_dir / ".git"
    if not git_dir.exists():
        return True

    import subprocess

    print("\n==================================================")
    print("🛡️ [PRE-FLIGHT GUARD] Memeriksa Keselarasan Upstream Git...")
    print("==================================================")

    try:
        # 1. Fetch origin main with polite timeout
        res_fetch = subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        if res_fetch.returncode != 0:
            print("⚠️ [PRE-FLIGHT GUARD] Gagal fetch origin/main (mungkin offline). Melanjutkan dengan DB lokal.")
            return True

        # 2. Check if local is behind origin/main
        res_behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        behind_count = int(res_behind.stdout.strip() or "0")

        if behind_count > 0:
            print(f"⚡ [PRE-FLIGHT GUARD] Terdeteksi {behind_count} commit baru dari Cloud Bot di origin/main!")
            print("   • Menarik database master & kode terbaru (git pull --rebase)...")
            res_pull = subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=15
            )
            if res_pull.returncode == 0:
                print("   ✅ Berhasil sinkronisasi upstream!")
                try:
                    from sync_repos import sync_master_db
                    sync_master_db()
                    print("   ✅ Database lokal berhasil direplikasi ke seluruh repo holding.")
                except Exception as e:
                    print(f"   ⚠️ Replikasi notice: {e}")
            else:
                print(f"   ⚠️ Git pull warning: {res_pull.stderr.strip()}")
        else:
            print("✅ [PRE-FLIGHT GUARD] Database lokal sudah 100% selaras dengan Cloud upstream (0 commit behind).")

        return True
    except subprocess.TimeoutExpired:
        print("⚠️ [PRE-FLIGHT GUARD] Timeout memeriksa upstream (koneksi lambat). Melanjutkan dengan DB lokal.")
        return True
    except Exception as e:
        print(f"ℹ️ [PRE-FLIGHT GUARD] Notice: {e}")
        return True

def main():
    parser = argparse.ArgumentParser(
        description="BBKitchen Sovereign Ingestion Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bbk_pipeline.py normalize --limit 10   # Test normalize 10 pending items
  python bbk_pipeline.py sync                   # Replicate master SQLite db to repos
  python bbk_pipeline.py sync --master          # Sync categories & warehouses SSOT
  python bbk_pipeline.py run-all                # Execute fetch -> normalize -> sync
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Pipeline operation mode")

    # Command: fetch
    parser_fetch = subparsers.add_parser("fetch", help="Fetch raw messages from Telegram partner channels")
    parser_fetch.add_argument("--days", type=int, default=1, help="Number of lookback days for Telegram fetch")
    parser_fetch.add_argument("--limit", type=int, default=50, help="Maximum messages to fetch per channel")
    parser_fetch.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    parser_fetch.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")

    # Command: normalize
    parser_norm = subparsers.add_parser("normalize", help="Process raw items with AI & SSOT taxonomy")
    parser_norm.add_argument("--limit", type=int, default=None, help="Limit number of raw records to process")
    parser_norm.add_argument("--dry-run", action="store_true", help="Dry run without writing to SQLite")

    # Command: sync
    parser_sync = subparsers.add_parser("sync", help="Replicate master SQLite bbk.db across sovereign repositories (bbk-storefront, bbk-control-tower, Jarvis-OS)")

    # Command: heal
    parser_heal = subparsers.add_parser("heal", help="Heal and re-enrich legacy catalog with Pure Gemini Multimodal AI")
    parser_heal.add_argument("--sku", type=str, default=None, help="Target specific SKU(s), comma-separated")
    parser_heal.add_argument("--anomalies-only", action="store_true", help="Target only detected anomaly records")
    parser_heal.add_argument("--limit", type=int, default=None, help="Limit number of items to heal")
    parser_heal.add_argument("--dry-run", action="store_true", help="Dry run without writing to DB")
    parser_heal.add_argument("--resume", action="store_true", help="Resume from last checkpoint")

    # Command: upload-r2
    parser_r2 = subparsers.add_parser("upload-r2", help="Upload WebP photos to Cloudflare R2 bucket")
    parser_r2.add_argument("--no-purge", action="store_true", help="Keep ephemeral buffer without purging")

    # Command: run-all
    parser_all = subparsers.add_parser("run-all", help="Execute complete automated pipeline (fetch -> normalize -> sync -> upload-r2)")
    parser_all.add_argument("--days", type=int, default=1, help="Number of lookback days for Telegram fetch (default: 1)")
    parser_all.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    parser_all.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")

    parser.add_argument("--no-sync", action="store_true", help="Bypass automatic pre-flight upstream git sync")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Pre-Flight Anti-Collision Guard
    if args.command in ("fetch", "normalize", "run-all"):
        ensure_preflight_sync(no_sync=getattr(args, "no_sync", False))

    if args.command == "fetch":
        print("=== [STEP 1/4] Fetching from Telegram Channels ===")
        try:
            from telethon_fetch import main as telethon_main
            f_args = []
            if args.start and args.end:
                f_args = ["--start", args.start, "--end", args.end]
            telethon_main(days=args.days, args_list=f_args if f_args else None)
        except Exception as e:
            print(f"[ERROR] Fetch execution failed: {e}")

    elif args.command == "normalize":
        print("=== [STEP 2/4] Normalizing Raw Pipeline with SSOT ===")
        from process_raw_pipeline import run_pipeline
        run_pipeline(dry_run=args.dry_run, limit=args.limit)

    elif args.command == "sync":
        print("=== [STEP 3/4] Replicating Master SQLite to Repositories ===")
        from sync_repos import sync_master_db
        sync_master_db()

    elif args.command == "heal":
        print("=== [BULK HEALER] Healing Legacy Catalog with Pure Gemini Multimodal AI ===")
        import subprocess
        cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core", "enrich_holver_bulk.py")]
        if args.sku:
            cmd.extend(["--sku", args.sku])
        if args.anomalies_only:
            cmd.append("--anomalies-only")
        if args.limit:
            cmd.extend(["--limit", str(args.limit)])
        if args.dry_run:
            cmd.append("--dry-run")
        if args.resume:
            cmd.append("--resume")
        subprocess.run(cmd)

    elif args.command == "upload-r2":
        print("=== [STEP 4/4] Uploading Master WebP Photos to Cloudflare R2 ===")
        from sync_photos_to_r2 import main as r2_main
        r2_main(auto_purge=not args.no_purge)

    elif args.command == "run-all":
        print("==================================================")
        print("👑 BBKitchen Sovereign Automated Pipeline Execution")
        print("==================================================")
        
        # 1. Fetch
        range_str = f"{args.start} s/d {args.end}" if (args.start and args.end) else f"Lookback: {args.days} hari"
        print(f"\n--- 1. Fetching Telegram Messages ({range_str}) ---")
        try:
            from telethon_fetch import main as telethon_main
            f_args = []
            if args.start and args.end:
                f_args = ["--start", args.start, "--end", args.end]
            telethon_main(days=args.days, args_list=f_args if f_args else None)
        except Exception as e:
            print(f"[WARN] Fetch step skipped or encountered warning: {e}")

        # 2. Normalize
        print("\n--- 2. Normalizing Catalog with AI & SSOT ---")
        from process_raw_pipeline import run_pipeline
        run_pipeline(dry_run=False)

        # 3. Sync
        print("\n--- 3. Replicating Master SQLite to Repositories ---")
        from sync_repos import sync_master_db
        sync_master_db()

        # 4. Upload to Cloudflare R2 & Auto-Purge
        print("\n--- 4. Syncing Master WebP Photos to Cloudflare R2 ---")
        try:
            from sync_photos_to_r2 import main as r2_main
            r2_main(auto_purge=True)
        except Exception as e:
            print(f"[WARN] Cloudflare R2 sync step encountered notice: {e}")

        print("\n✅ Sovereign Pipeline Run Complete.")

if __name__ == "__main__":
    main()
