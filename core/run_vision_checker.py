# -*- coding: utf-8 -*-
"""
👑 BBKitchen Sovereign Autonomous Vision & Photo Desync Checker (run_vision_checker.py)
Sub-Modul 2.11 / Task 2.11.5 - Autonomous Physical Photo Verification via Gemini Vision
"""

import os
import sys
import json
import time
import base64
import sqlite3
import requests
import argparse
from typing import Dict, Any, Optional, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
for p in [CURRENT_DIR, PARENT_DIR]:
    if p not in sys.path:
        sys.path.append(p)

from ai_gateway import load_env
from normalize_engine import OFFICIAL_CATEGORY_SLUGS, CAT_SSOT

load_env()

JARVIS_DB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db"))
CHECKPOINT_FILE = os.path.join(CURRENT_DIR, "vision_checkpoint.json")
REPORT_FILE = os.path.join(CURRENT_DIR, "vision_sync_report.json")

HOLVER_KEY = os.getenv("HOLVER_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
R2_BASE_URL = "https://pub-946d1fe1a1b1461eb2cca6be4462ba11.r2.dev"

SYSTEM_PROMPT = """Anda adalah Senior Visual Equipment Inspector untuk BBKitchen (Pusat Peralatan Dapur Komersial Restoran Second Terbesar di Indonesia).
Tugas Anda: Memeriksa FOTO FISIK ALAT ini secara objektif dan mengekstrak jenis fisik alat yang sesungguhnya.

PERIKSA SECARA TELITI:
1. Apa nama alat dan kategori fisik yang tampak di foto? (misal: "Kompor Kwali 2 Burner", "Undercounter Chiller 2 Pintu", "Meja Stainless 2 Susun", "Exhaust Hood", "Single Sink").
2. Apakah tampak stiker/plat merk tertentu? (misal: GEA, Nayati, Fomac, Getra, Escoffier, atau Tanpa Merk/Fabrikasi).
3. Kondisi fisik yang terlihat (0-100% dan catatan fisik).
4. Fitur visual utama (misal: ada kompresor, ada bak cuci, ada roda, ada burner api, ada pintu geser, ada backsplash).

KEMBALIKAN STRICTLY JSON DENGAN FORMAT:
{
  "nama_alat_visual": "Nama alat fisik yang terlihat jelas di foto",
  "kategori_visual_slug": "<pilih salah satu slug 66-SSOT yang paling cocok>",
  "merk_terlihat": "Nama brand jika terbaca di foto atau null",
  "estimasi_kondisi_persen": 85,
  "fitur_utama": ["fitur 1", "fitur 2"],
  "is_valid_kitchen_equipment": true,
  "catatan_inspeksi": "Deskripsi singkat penampakan visual"
}
"""

def call_gemini_vision(img_url: str, prompt_text: str = SYSTEM_PROMPT) -> Optional[Dict[str, Any]]:
    # Tier 1: Try Holver.id gemini-3.8-flash
    if HOLVER_KEY:
        try:
            url = "https://api.holver.id/v1/chat/completions"
            headers = {"Authorization": f"Bearer {HOLVER_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "gemini-3.8-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": img_url}}
                        ]
                    }
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                raw = res.json()["choices"][0]["message"]["content"]
                if "```" in raw:
                    raw = raw.split("```")[1].replace("json", "").strip()
                return json.loads(raw)
        except Exception:
            pass

    # Tier 2: Google AI Studio gemini-3-flash-preview
    if GEMINI_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_KEY}"
            prompt_with_url = f"{prompt_text}\n\nPeriksa foto di URL ini: {img_url}"
            payload = {
                "contents": [{"parts": [{"text": prompt_with_url}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}
            }
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                raw = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw)
        except Exception:
            pass

    return None

def run_vision_sweep(limit: Optional[int] = None, resume: bool = True):
    print("=" * 64)
    print("👁️ BBKITCHEN AUTONOMOUS VISION & PHOTO DESYNC CHECKER")
    print(f"Target Database : {JARVIS_DB_PATH}")
    print(f"Vision Engine   : Gemini Vision (Holver.id ➔ Google AI Studio)")
    print("=" * 64)

    conn = sqlite3.connect(JARVIS_DB_PATH, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=60000;")

    # Load checkpoint
    processed_skus = set()
    if resume and os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                chk = json.load(f)
                processed_skus = set(chk.get("completed_skus", []))
        except Exception:
            pass

    query = """
        SELECT sku, title, category_slug, featured_image, photo_urls, link_telegram
        FROM products
        ORDER BY CAST(SUBSTR(sku, 4) AS INTEGER) ASC
    """
    rows = conn.execute(query).fetchall()
    total_rows = len(rows)

    pending_rows = [r for r in rows if r["sku"] not in processed_skus]
    if limit:
        pending_rows = pending_rows[:limit]

    print(f"📋 Total Produk: {total_rows} | Sudah Diinspeksi: {len(processed_skus)} | Antrean: {len(pending_rows)}")

    desync_count = 0
    synced_count = 0
    skipped_count = 0
    report_items = []

    start_time = time.time()
    idx = 0

    for row in pending_rows:
        idx += 1
        sku = row["sku"]
        title = row["title"]
        cat_slug = row["category_slug"] or ""
        photos_str = str(row["photo_urls"] or row["featured_image"] or "").strip()

        # Resolve primary photo URL
        photo_filename = f"{sku}_1.webp"
        if photos_str and not photos_str.startswith("http"):
            first_part = photos_str.split("|")[0].split(",")[0].strip()
            if first_part.endswith((".webp", ".jpg", ".png", ".jpeg")):
                photo_filename = first_part

        img_url = f"{R2_BASE_URL}/{photo_filename}" if not photo_filename.startswith("http") else photo_filename

        # Vision call
        vision_res = call_gemini_vision(img_url)

        if not vision_res or "error" in vision_res:
            # Fallback placeholder inspection if network / image unavailable
            vision_status = "SKIPPED_NO_IMAGE"
            vision_cat = cat_slug
            fitur_str = "[]"
            kondisi_pct = 85
            catatan = "Gambar tidak dapat diakses secara langsung"
            desync_flag = 0
            skipped_count += 1
        else:
            vision_cat = vision_res.get("kategori_visual_slug", "").strip().lower()
            kondisi_pct = vision_res.get("estimasi_kondisi_persen", 85)
            fitur_list = vision_res.get("fitur_utama", [])
            fitur_str = json.dumps(fitur_list, ensure_ascii=False)
            catatan = vision_res.get("catatan_inspeksi", "")
            brand_vis = vision_res.get("merk_terlihat")

            # Check if category desynced
            is_desynced = False
            if vision_cat and cat_slug and vision_cat != cat_slug:
                # Discrepancy detected
                is_desynced = True
                desync_count += 1
                desync_flag = 1
                vision_status = "DESYNC_MISMATCH"
                reconcile_note = f"VISUAL_MISMATCH: Foto={vision_cat}, DB={cat_slug}"
            else:
                synced_count += 1
                desync_flag = 0
                vision_status = "VERIFIED_SYNCED"
                reconcile_note = "PHOTO_MATCHED"

            # Update master SQLite
            conn.execute("""
                UPDATE products
                SET ai_vision_status = ?,
                    vision_kategori_slug = ?,
                    vision_fitur_utama = ?,
                    vision_kondisi_persen = ?,
                    vision_catatan = ?,
                    photo_desync_flag = ?,
                    reconciliation_log = ?
                WHERE sku = ?
            """, (vision_status, vision_cat, fitur_str, kondisi_pct, catatan, desync_flag, reconcile_note, sku))

        processed_skus.add(sku)

        # Progress bar
        curr_total = len(processed_skus)
        pct = (curr_total / total_rows) * 100
        elapsed = time.time() - start_time
        sec_per_it = elapsed / idx if idx > 0 else 0
        rem_sec = (total_rows - curr_total) * sec_per_it
        eta_str = f"{int(rem_sec // 60)}m {int(rem_sec % 60)}s"

        bar_len = 15
        filled = int(bar_len * curr_total // total_rows)
        bar = "█" * filled + "░" * (bar_len - filled)

        status_icon = "🟢" if desync_flag == 0 else "🔴 DESYNC"
        print(f"⚡ [{bar}] {pct:.1f}% ({curr_total}/{total_rows}) • ETA: ~{eta_str} • SKU: {sku} ({status_icon})")
        if desync_flag == 1:
            print(f"   ⚠️ MISMATCH DETECTED: DB=[{cat_slug}] vs Foto=[{vision_cat}] ({catatan[:60]}...)")

        # Checkpoint every 20 items
        if idx % 20 == 0 or idx == len(pending_rows):
            conn.commit()
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "last_processed_sku": sku,
                    "total_processed": len(processed_skus),
                    "completed_skus": list(processed_skus),
                    "desync_count": desync_count,
                    "synced_count": synced_count,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }, f, indent=2)

    conn.commit()
    conn.close()
    print("=" * 64)
    print(f"🏁 VISION SWEEP COMPLETED! Total: {total_rows} | Synced: {synced_count} | Desync: {desync_count}")
    print("=" * 64)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BBKitchen Vision & Photo Desync Checker")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of units to process")
    parser.add_argument("--no-resume", action="store_true", help="Start from beginning without resume")
    args = parser.parse_args()

    run_vision_sweep(limit=args.limit, resume=not args.no_resume)
