# -*- coding: utf-8 -*-
"""
👑 BBKitchen Sovereign Holver.id & Multi-Provider Bulk Healer (enrich_holver_bulk.py)
Sub-Modul 2.11 / Task 2.11.4 - Bulk Legacy Healing & Semantic Normalization Engine

Features:
1. Sacred Slug Immutability (SSOT Rule #25): Kunci mati permalink Google Search Console (Zero 404).
2. 5-Layer Semantic Healing: Title kanonikal berdimensi, taksonomi 58 kategori SSOT, anti-jebakan biner,
   rich HTML description bersih tanpa box duplikat, dan 4-tier image alt text suite.
3. Pure Gemini Gateway: Google AI Studio Direct -> Holver.id Gemini Gateway (Zero DeepSeek).
4. Checkpointing & Resumability: Track state in checkpoint file with batch commits.
5. Dual DB Auto-Sync: Updates both Jarvis-OS master bbk.db and bbk-storefront/data/bbk.db.
"""

import os
import re
import sys
import json
import time
import shutil
import sqlite3
import argparse
from typing import Dict, Any, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
for p in [CURRENT_DIR, PARENT_DIR]:
    if p not in sys.path:
        sys.path.append(p)

from ai_gateway import AIGateway, load_env
from normalize_engine import (
    normalize_single_caption,
    format_rupiah,
    load_ssot_taxonomy,
    OFFICIAL_CATEGORY_SLUGS
)

load_env()

# Canonical DB Paths
JARVIS_DB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db"))
STOREFRONT_DB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "bbk-storefront", "data", "bbk.db"))
LOCAL_DB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "bbk.db"))

CHECKPOINT_FILE = os.path.join(CURRENT_DIR, "enrich_checkpoint.json")

def get_primary_db_path() -> str:
    if os.path.exists(JARVIS_DB_PATH):
        return JARVIS_DB_PATH
    if os.path.exists(STOREFRONT_DB_PATH):
        return STOREFRONT_DB_PATH
    return LOCAL_DB_PATH

def sync_to_storefront_db():
    src = get_primary_db_path()
    if os.path.exists(src) and os.path.exists(os.path.dirname(STOREFRONT_DB_PATH)):
        try:
            src_conn = sqlite3.connect(src, timeout=60.0)
            dst_conn = sqlite3.connect(STOREFRONT_DB_PATH, timeout=60.0)
            with dst_conn:
                src_conn.backup(dst_conn)
            src_conn.close()
            dst_conn.close()
            print(f"📦 [DB SYNC] Successfully synced master SQLite to {STOREFRONT_DB_PATH} via atomic backup API", flush=True)
        except Exception as e:
            print(f"⚠️ [DB SYNC WARNING] Failed copying to storefront DB: {e}", flush=True)

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_processed_sku": None, "total_processed": 0, "completed_skus": []}

def save_checkpoint(last_sku: str, total_count: int, completed_skus: List[str]):
    try:
        data = {
            "last_processed_sku": last_sku,
            "total_processed": total_count,
            "completed_skus": completed_skus[-1000:], # keep recent 1000
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"⚠️ [CHECKPOINT ERROR] Could not save checkpoint: {e}")

def fetch_products_to_enrich(
    conn: sqlite3.Connection,
    target_skus: Optional[List[str]] = None,
    anomalies_only: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
    resume: bool = False,
    checkpoint: Optional[dict] = None
) -> List[sqlite3.Row]:
    cur = conn.cursor()

    if target_skus:
        placeholders = ",".join(["?"] * len(target_skus))
        query = f"""
            SELECT p.*, r.caption_raw, r.source_group, r.link_message, r.photo_urls, r.lokasi_gudang
            FROM products p
            LEFT JOIN raw_pipeline r ON p.sku = r.kode_unit
            WHERE p.sku IN ({placeholders})
            ORDER BY CAST(SUBSTR(p.sku, 4) AS INTEGER) ASC
        """
        return cur.execute(query, target_skus).fetchall()

    if anomalies_only:
        # Known anomaly query: mismatched categories, missing dimensions in titles, or suspected wrong door counts
        query = """
            SELECT p.*, r.caption_raw, r.source_group, r.link_message, r.photo_urls, r.lokasi_gudang
            FROM products p
            LEFT JOIN raw_pipeline r ON p.sku = r.kode_unit
            WHERE (
                (p.category_slug LIKE '%showcase%' AND (r.caption_raw LIKE '%2 pintu%' OR r.caption_raw LIKE '%2p%' OR r.caption_raw LIKE '%3 pintu%') AND p.category_slug = 'showcase-1-pintu')
                OR (p.category_slug LIKE '%meja%' AND (r.caption_raw LIKE '%1 susun%' OR r.caption_raw LIKE '%1 trap%') AND p.category_slug = 'meja-2-susun-stainless')
                OR (p.category_slug LIKE '%meja%' AND (r.caption_raw LIKE '%3 susun%' OR r.caption_raw LIKE '%3 trap%') AND p.category_slug = 'meja-2-susun-stainless')
                OR (r.caption_raw LIKE '%oven%' AND (r.caption_raw LIKE '%kompor%' OR r.caption_raw LIKE '%tungku%') AND p.category_slug = 'oven')
                OR (p.category_slug = 'peralatan-dapur-bekas-lainnya')
                OR (p.title LIKE '%bekas bekas%')
                OR (p.harga_modal > 100000000)
            )
            ORDER BY CAST(SUBSTR(p.sku, 4) AS INTEGER) ASC
        """
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        return cur.execute(query).fetchall()

    query = """
        SELECT p.*, r.caption_raw, r.source_group, r.link_message, r.photo_urls, r.lokasi_gudang
        FROM products p
        LEFT JOIN raw_pipeline r ON p.sku = r.kode_unit
        ORDER BY CAST(SUBSTR(p.sku, 4) AS INTEGER) ASC
    """
    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"
    
    rows = cur.execute(query).fetchall()

    if resume and checkpoint and checkpoint.get("last_processed_sku"):
        last_sku = checkpoint["last_processed_sku"]
        try:
            last_num = int(last_sku.replace("BBK", ""))
            rows = [r for r in rows if int(r["sku"].replace("BBK", "")) > last_num]
        except Exception:
            pass

    return rows

def heal_product_record(row: sqlite3.Row, gateway: AIGateway) -> Dict[str, Any]:
    sku = row["sku"]
    existing_slug = row["slug"] # SACRED SLUG - NEVER OVERWRITE
    caption_raw = row["caption_raw"] or row["title"] or ""
    source_group = str(row["source_group"] or row["asal_gudang"] or "")
    link_message = str(row["link_message"] or row["link_telegram"] or "")
    lokasi_gudang = str(row["lokasi_gudang"] or row["lokasi_unit"] or "")
    photo_urls = str(row["photo_urls"] or row["featured_image"] or "")

    # Execute 5-Layer Normalization
    normalized = normalize_single_caption(
        raw_caption=caption_raw,
        sku=sku,
        existing_slug=existing_slug,
        source_group=source_group,
        link_message=link_message,
        location_override=lokasi_gudang,
        photo_urls=photo_urls,
        gateway=gateway
    )

    # Double check slug lock
    if normalized["slug"] != existing_slug and existing_slug:
        normalized["slug"] = existing_slug
        normalized["link_unit"] = f"https://bukanbarukitchen.com/shop/{existing_slug}/"

    return normalized

def update_product_in_db(conn: sqlite3.Connection, record: Dict[str, Any]):
    cur = conn.cursor()
    update_sql = """
        UPDATE products SET
            title = ?,
            seo_title = ?,
            category_slug = ?,
            garansi = ?,
            status_unit = ?,
            status_pipeline = ?,
            lokasi_unit = ?,
            kondisi_unit = ?,
            short_description = ?,
            full_description = ?,
            spesifikasi_ringkas = ?,
            yoast_keyword = ?,
            yoast_description = ?,
            harga_modal = ?,
            harga_buka_wa = ?,
            harga_deal_wa = ?,
            harga_floor_wa = ?,
            margin_floor = ?,
            margin_deal = ?,
            status_guardrail = ?,
            estimasi_harga_baru = ?,
            harga_display_low = ?,
            harga_display_high = ?,
            image_alt = ?,
            image_title = ?,
            image_caption = ?,
            image_description = ?,
            normalization_source = 'PURE_GEMINI',
            ai_enrichment_status = 'COMPLETED',
            ai_enrich_status = 'COMPLETED',
            is_dirty = 1,
            updated_at = ?
        WHERE sku = ?
    """
    raw_specs = record.get("spesifikasi_ringkas", [])
    specs_json = json.dumps(raw_specs) if isinstance(raw_specs, list) else str(raw_specs or "[]")

    params = (
        record["title"],
        record["seo_title"],
        record["category_slug"],
        record["garansi"],
        record["status_unit"],
        record["status_pipeline"],
        record["lokasi_unit"],
        record["kondisi_unit"],
        record["short_description"],
        record["full_description"],
        specs_json,
        record["yoast_keyword"],
        record["yoast_description"],
        record["harga_modal"],
        record["harga_buka_wa"],
        record["harga_deal_wa"],
        record["harga_floor_wa"],
        record["margin_floor"],
        record["margin_deal"],
        record["status_guardrail"],
        record["estimasi_harga_baru"],
        record["harga_display_low"],
        record["harga_display_high"],
        record["image_alt"],
        record["image_title"],
        record["image_caption"],
        record["image_description"],
        time.strftime("%Y-%m-%d %H:%M:%S"),
        record["sku"]
    )
    cur.execute(update_sql, params)

def format_progress_bar(current: int, total: int, width: int = 15) -> str:
    pct = (current / total) if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:.1f}%"

def main():
    parser = argparse.ArgumentParser(description="BBKitchen Holver.id & Multi-Provider Bulk Healer")
    parser.add_argument("--dry-run", action="store_true", help="Simulate normalization without DB mutation")
    parser.add_argument("--sku", type=str, default=None, help="Target specific SKU(s), comma-separated (e.g. BBK3188,BBK1508)")
    parser.add_argument("--anomalies-only", action="store_true", help="Target only detected anomaly records")
    parser.add_argument("--limit", type=int, default=None, help="Max records to process")
    parser.add_argument("--offset", type=int, default=0, help="Offset records")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--reset-checkpoint", action="store_true", help="Reset checkpoint file")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch commit frequency")
    args = parser.parse_args()

    if args.reset_checkpoint and os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("🔄 [CHECKPOINT] Checkpoint reset.", flush=True)

    checkpoint = load_checkpoint() if args.resume else {}
    target_skus = [s.strip().upper() for s in args.sku.split(",")] if args.sku else None

    db_path = get_primary_db_path()
    print(f"================================================================", flush=True)
    print(f"👑 BBKITCHEN BULK HEALER & SEMANTIC ENRICHMENT ENGINE", flush=True)
    print(f"Database Target : {db_path}", flush=True)
    print(f"Mode            : {'DRY-RUN (Simulasi)' if args.dry_run else 'LIVE MUTATION (Write to SQLite)'}", flush=True)
    print(f"Filter          : {'SKU: ' + str(target_skus) if target_skus else ('ANOMALIES ONLY' if args.anomalies_only else 'ALL CATALOG')}", flush=True)
    print(f"Limit / Offset  : Limit {args.limit or 'ALL'}, Offset {args.offset}", flush=True)
    print(f"================================================================", flush=True)

    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=60000;")

    rows = fetch_products_to_enrich(
        conn=conn,
        target_skus=target_skus,
        anomalies_only=args.anomalies_only,
        limit=args.limit,
        offset=args.offset,
        resume=args.resume,
        checkpoint=checkpoint
    )

    total_rows = len(rows)
    total_catalog_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    already_healed = conn.execute("SELECT COUNT(*) FROM products WHERE ai_enrichment_status = 'COMPLETED'").fetchone()[0]

    print(f"📋 Queued for Healing: {total_rows} records (Already Healed: {already_healed}/{total_catalog_count})\n", flush=True)
    if total_rows == 0:
        print("✅ No records match the query criteria. Exiting cleanly.", flush=True)
        conn.close()
        return

    gateway = AIGateway()
    completed_skus = checkpoint.get("completed_skus", [])
    success_count = 0
    fail_count = 0
    start_time = time.time()

    for idx, r in enumerate(rows, 1):
        sku = r["sku"]
        old_title = r["title"]
        old_cat = r["category_slug"]
        old_modal = r["harga_modal"]
        old_slug = r["slug"]

        elapsed = time.time() - start_time
        speed = elapsed / max(1, idx)
        eta_sec = (total_rows - idx) * speed
        eta_str = f"{int(eta_sec // 60)}m {int(eta_sec % 60)}s" if eta_sec < 3600 else f"{eta_sec/3600:.1f}h"
        
        current_overall = already_healed + idx
        pbar = format_progress_bar(current_overall, total_catalog_count, 15)

        print(f"\n⚡ {pbar} ({current_overall}/{total_catalog_count}) • ETA: ~{eta_str} ({speed:.1f}s/it) • SKU: {sku} ({old_slug})", flush=True)
        try:
            healed = heal_product_record(r, gateway)

            # Verification of Sacred Rules
            assert healed["slug"] == old_slug, f"CRITICAL SLUG MUTATION DETECTED: {old_slug} -> {healed['slug']}"
            assert healed["category_slug"] in OFFICIAL_CATEGORY_SLUGS, f"INVALID CATEGORY SLUG: {healed['category_slug']}"

            # Diff summary
            title_diff = f"'{old_title}' ➔ '{healed['title']}'" if old_title != healed["title"] else f"'{healed['title']}' (Retained)"
            cat_diff = f"[{old_cat}] ➔ [{healed['category_slug']}]" if old_cat != healed["category_slug"] else f"[{healed['category_slug']}]"
            modal_diff = f"{format_rupiah(old_modal)} ➔ {format_rupiah(healed['harga_modal'])}"

            print(f"   🏷️ Title   : {title_diff}", flush=True)
            print(f"   📂 Category: {cat_diff}", flush=True)
            print(f"   💰 HPP     : {modal_diff} | Buka WA: {format_rupiah(healed['harga_buka_wa'])}", flush=True)
            print(f"   📈 Display : {format_rupiah(healed['harga_display_low'])} - {format_rupiah(healed['harga_display_high'])} (Baru: ~{format_rupiah(healed['estimasi_harga_baru'])})", flush=True)
            print(f"   🖼️ Alt Text: {healed['image_alt']}", flush=True)

            if not args.dry_run:
                update_product_in_db(conn, healed)
                completed_skus.append(sku)

                if idx % args.batch_size == 0 or idx == total_rows:
                    conn.commit()
                    save_checkpoint(sku, len(completed_skus), completed_skus)
                    print(f"   💾 [BATCH COMMIT] Committed {current_overall} / {total_catalog_count} records to SQLite.", flush=True)

            success_count += 1
            # Rate limit politeness
            time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n🛑 [USER INTERRUPTION] Halting bulk healer cleanly...")
            if not args.dry_run:
                conn.commit()
                save_checkpoint(sku, len(completed_skus), completed_skus)
                print(f"💾 State saved up to {sku}.")
            break
        except Exception as e:
            print(f"   ❌ [ERROR] Failed healing {sku}: {e}")
            fail_count += 1

    if not args.dry_run:
        conn.commit()
        sync_to_storefront_db()
        try:
            from generate_quality_matrix import generate_html_report
            generate_html_report()
        except Exception as e:
            print(f"⚠️ [QUALITY REPORT ERROR] Failed to generate dashboard: {e}")

    conn.close()
    elapsed = time.time() - start_time
    print(f"\n================================================================")
    print(f"🏁 BULK HEALER FINISHED in {elapsed:.1f}s")
    print(f"Success: {success_count} | Failed: {fail_count} | Total: {total_rows}")
    print(f"================================================================")

if __name__ == "__main__":
    main()
