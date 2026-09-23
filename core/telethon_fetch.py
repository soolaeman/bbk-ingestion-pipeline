# -*- coding: utf-8 -*-
"""
👑 BBKitchen Sovereign Telegram Fetcher & Anti-Duplicate Raw Ingestion Engine
Fetches raw messages, downloads media, groups album posts, prevents duplicates via Telegram Link SSOT,
and populates raw_pipeline in SQLite.
"""

import os
import sys
import json
import sqlite3
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from telethon import TelegramClient
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
EXPORT_ROOT = BASE_DIR / "exports"
LOCAL_TZ = ZoneInfo("Asia/Jakarta")

# Database Path Resolution (Canonical Jarvis-OS or local)
LOCAL_DB_PATH = BASE_DIR.parent / "bbk.db"
JARVIS_DB_PATH = BASE_DIR.parent.parent / "Jarvis-OS" / "domains" / "business" / "bbkitchen" / "data" / "bbk.db"
DB_PATH = JARVIS_DB_PATH if JARVIS_DB_PATH.exists() else LOCAL_DB_PATH

# Config SSOT Path Resolution
LOCAL_CONFIG_DIR = BASE_DIR.parent / "config"
JARVIS_CONFIG_DIR = BASE_DIR.parent.parent / "Jarvis-OS" / "domains" / "business" / "bbkitchen" / "config"
CONFIG_DIR = JARVIS_CONFIG_DIR if JARVIS_CONFIG_DIR.exists() else LOCAL_CONFIG_DIR

from config_telethon import API_ID, API_HASH, SESSION_NAME
from watermark_engine import process_watermark_and_webp

SOURCE_MAP = {
    "GK": -1002479885293,
    "BB": -1001947492349,
    "SM": -1002249769366,
    "BL": -1002221612633,
    "ML": -1002295735681,
    "PY": -1002556966592,
    "PE": -1002471308578,
    "WT": -1002559367434,
    "ON": -1003420173563,
    "RB": -1002405866006,
    "RK": -1004326430608,      # Rizki Kitchen (Rawakalong Bogor)
    "SK": -1003506626675,      # Sanjaya Kitchen (Sawangan Depok)
    "KG": -1002375036806,      # Kitchen Gembel (Pamulang Barat)
}

def load_warehouse_locations():
    wh_file = CONFIG_DIR / "warehouses_ssot.json"
    loc_map = {}
    if wh_file.exists():
        with open(wh_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for code, p in data.get("partners", {}).items():
                loc_map[code] = p.get("location", "PAMULANG 2, TANGSEL")
    return loc_map

WAREHOUSE_LOCATIONS = load_warehouse_locations()

# ================= TELETHON CLIENT & PRE-CHECK =================
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH
)

def load_r2_uploaded_cache():
    cache_file = BASE_DIR / "r2_uploaded_cache.txt"
    legacy_cache = BASE_DIR.parent / "archive" / "legacy_gsheet_pipeline" / "r2_uploaded_cache.txt"
    uploaded = set()
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            uploaded.update(line.strip() for line in f if line.strip())
    if legacy_cache.exists():
        with open(legacy_cache, "r", encoding="utf-8") as f:
            uploaded.update(line.strip() for line in f if line.strip())
    return uploaded

def get_existing_links():
    """
    Mengambil Telegram link yang sudah terdaftar DAN fotonya sudah verified ada di R2.
    Jika ada unit di DB yang fotonya belum masuk R2, link TIDAK di-skip agar Cloud runner otomatis menambal foto (Self-Healing).
    """
    if not DB_PATH.exists():
        return set()

    r2_cache = load_r2_uploaded_cache()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    valid_links = set()
    # 1. Dari products: Hanya skip jika fotonya sudah terverifikasi ada di Cloudflare R2
    cur.execute("SELECT link_telegram, featured_image FROM products WHERE link_telegram IS NOT NULL AND link_telegram != ''")
    for link, feat_img in cur.fetchall():
        if not r2_cache or (feat_img and feat_img in r2_cache):
            valid_links.add(link)

    # 2. Dari raw_pipeline yang masih pending (is_processed = 0)
    cur.execute("SELECT link_message FROM raw_pipeline WHERE is_processed = 0 AND link_message IS NOT NULL")
    for row in cur.fetchall():
        valid_links.add(row[0])

    conn.close()
    return valid_links

async def fetch_group(src_code, chat_id, start_date, end_date, existing_links):
    out_dir = EXPORT_ROOT / src_code
    out_dir.mkdir(parents=True, exist_ok=True)

    chat_clean = str(chat_id).replace("-100", "").replace("-", "")
    base_url = f"https://t.me/c/{chat_clean}"

    messages = []
    skipped_dupes = 0
    pbar = tqdm(desc=f"Scanning [{src_code}]", unit=" msg", leave=False)

    async for msg in client.iter_messages(chat_id, offset_date=end_date):
        pbar.update(1)
        if not msg.date:
            continue
        if msg.date < start_date:
            break
        if not msg.photo:
            continue

        # PRE-DOWNLOAD ANTI-DUPLICATE CHECK (Instant 0.001s skip, Zero Bandwidth Waste)
        msg_link = f"{base_url}/{msg.id}"
        if msg_link in existing_links:
            skipped_dupes += 1
            continue

        target_file = out_dir / f"{msg.id}.jpg"
        if target_file.exists() and target_file.stat().st_size > 0:
            photo_path = target_file
        else:
            photo_path = await msg.download_media(target_file)

        messages.append({
            "id": msg.id,
            "grouped_id": msg.grouped_id,
            "type": "message",
            "date": msg.date.isoformat(),
            "date_unixtime": int(msg.date.timestamp()),
            "text": msg.text or "",
            "photo": Path(photo_path).name if photo_path else ""
        })

    pbar.close()

    with open(out_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump({"messages": messages}, f, ensure_ascii=False, indent=2)

    if messages:
        print(f"[{src_code}] Mengambil {len(messages)} pesan baru ({skipped_dupes} duplikat di-skip).")
    else:
        print(f"[{src_code}] Bersih: 0 pesan baru ({skipped_dupes} duplikat di-skip).")

# ================= ANTI-DUPLICATE INGESTION ENGINE =================

def parse_telegram_text(raw_text):
    if isinstance(raw_text, str):
        return " ".join(raw_text.split())
    if isinstance(raw_text, list):
        parts = [item.get("text", "") if isinstance(item, dict) else item for item in raw_text]
        return " ".join("".join(parts).split())
    return ""

def group_raw_messages(src_code, time_window=15):
    folder = EXPORT_ROOT / src_code
    path = folder / "result.json"
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    msgs = sorted([m for m in data.get("messages", []) if m.get("type") == "message" and m.get("photo")], key=lambda x: x.get("id", 0))
    grouped = {}
    current_group = []
    last_ts = None
    group_index = 0

    for m in msgs:
        ts = int(m.get("date_unixtime", 0))
        if last_ts is None or abs(ts - last_ts) <= time_window:
            current_group.append(m)
        else:
            grouped[f"time_album_{group_index}"] = current_group
            group_index += 1
            current_group = [m]
        last_ts = ts

    if current_group:
        grouped[f"time_album_{group_index}"] = current_group

    chat_id = SOURCE_MAP.get(src_code, 0)
    clean_chat = str(chat_id).replace("-100", "").replace("-", "")
    base_url = f"https://t.me/c/{clean_chat}"

    units = []
    for group in grouped.values():
        text_candidates = [(m, parse_telegram_text(m.get("text", "")).strip()) for m in group if parse_telegram_text(m.get("text", ""))]
        if not text_candidates:
            continue
        cap_msg, caption = max(text_candidates, key=lambda x: len(x[1]))
        if len(caption) < 20:
            continue

        photos = [folder / m["photo"] for m in group if "photo" in m and (folder / m["photo"]).exists()]
        if photos:
            units.append({
                "link": f"{base_url}/{cap_msg['id']}",
                "caption": caption,
                "tanggal": datetime.fromtimestamp(int(cap_msg["date_unixtime"]), tz=timezone.utc).astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                "photos": photos,
                "src": src_code
            })

    return units

def ingest_exports_to_raw_pipeline():
    print("\n=======================================================")
    print("🛡️ BBK ANTI-DUPLICATE RAW INTAKE ENGINE (Telegram Link SSOT)")
    print("=======================================================")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Ambil seluruh Telegram link yang sudah pernah tercatat di DB (Anti-Duplikat Mutlak)
    existing_links = set(
        r[0] for r in cur.execute("""
            SELECT link_telegram FROM products WHERE link_telegram IS NOT NULL AND link_telegram != ''
            UNION
            SELECT link_message FROM raw_pipeline WHERE link_message IS NOT NULL AND link_message != ''
        """).fetchall() if r[0]
    )
    print(f"📊 Total link Telegram yang sudah terdaftar di SSOT: {len(existing_links)} link.")

    # 2. Hitung next SKU
    cur.execute("SELECT MAX(CAST(SUBSTR(sku, 4) AS INTEGER)) FROM products WHERE sku LIKE 'BBK%'")
    row_prod = cur.fetchone()
    max_prod = row_prod[0] if row_prod and row_prod[0] is not None else 0

    cur.execute("SELECT MAX(CAST(SUBSTR(kode_unit, 4) AS INTEGER)) FROM raw_pipeline WHERE kode_unit LIKE 'BBK%'")
    row_raw = cur.fetchone()
    max_raw = row_raw[0] if row_raw and row_raw[0] is not None else 0

    next_idx = max(max_prod, max_raw, 3097) + 1
    print(f"🔢 SKU selanjutnya dimulai dari: BBK{next_idx:04d}")

    # 3. Pure Cloud Ephemeral WebP Buffer (.temp_webp)
    ephemeral_webp = BASE_DIR.parent / ".temp_webp"
    ephemeral_webp.mkdir(parents=True, exist_ok=True)

    new_units_count = 0
    skipped_count = 0

    upsert_raw_sql = """
        INSERT INTO raw_pipeline (kode_unit, source_group, link_message, caption_raw, photo_urls, fetch_date, last_seen_date, lokasi_gudang, status_unit, is_processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(kode_unit) DO UPDATE SET
            link_message = excluded.link_message,
            caption_raw = excluded.caption_raw,
            photo_urls = excluded.photo_urls,
            last_seen_date = excluded.last_seen_date
    """

    for src_code in SOURCE_MAP.keys():
        units = group_raw_messages(src_code)
        for u in units:
            link = u["link"]
            # ANTI DUPLIKAT CHECK BERBASIS LINK TELEGRAM
            if link in existing_links:
                skipped_count += 1
                continue

            kode = f"BBK{next_idx:04d}"
            next_idx += 1

            # Watermark photos to WebP directly into ephemeral buffer
            photo_filenames = []
            for i, photo_path in enumerate(u["photos"], start=1):
                webp_name = f"{kode}_{i}.webp"
                dest_path = ephemeral_webp / webp_name
                process_watermark_and_webp(photo_path, dest_path)
                photo_filenames.append(webp_name)

            photo_urls_str = "|".join(photo_filenames)
            location_name = WAREHOUSE_LOCATIONS.get(src_code, "PAMULANG 2, TANGSEL")
            now_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")

            cur.execute(upsert_raw_sql, (
                kode,
                src_code,
                link,
                u["caption"],
                photo_urls_str,
                u["tanggal"],
                now_str,
                location_name,
                "READY",
                0  # is_processed = 0 (siap dinormalisasi AI)
            ))

            existing_links.add(link)
            new_units_count += 1
            print(f"  [+] Baru: {kode} ({src_code}) -> {link}")

    conn.commit()
    conn.close()

    print(f"\n✅ Selesai: {new_units_count} unit baru masuk raw_pipeline, {skipped_count} unit dilewati (duplikat link).")

# ================= MAIN =================

async def main_fetch(start_date, end_date):
    existing_links = get_existing_links()
    print(f"🛡️ Pre-Check SSOT: {len(existing_links)} link terdaftar (Anti-Duplicate Active).")
    await client.start()
    for src, chat_id in SOURCE_MAP.items():
        await fetch_group(src, chat_id, start_date, end_date, existing_links)
    await client.disconnect()

def main(days=None, args_list=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD")
    parser.add_argument("--start", help="YYYY-MM-DD")
    parser.add_argument("--end", help="YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=None, help="Number of lookback days")
    args, _ = parser.parse_known_args(args_list)

    def parse_local_dt(dt_str):
        return datetime.fromisoformat(dt_str).replace(tzinfo=LOCAL_TZ)

    if args.date:
        start_local = parse_local_dt(args.date).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
    elif args.start and args.end:
        start_local = parse_local_dt(args.start).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = parse_local_dt(args.end).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    else:
        effective_days = days if days is not None else (args.days if args.days is not None else 1)
        now_local = datetime.now(LOCAL_TZ)
        start_local = (now_local - timedelta(days=effective_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    start_date = start_local.astimezone(timezone.utc)
    end_date = end_local.astimezone(timezone.utc)

    print(f"WIB Range: {start_local.strftime('%Y-%m-%d %H:%M:%S')} -> {end_local.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Fetch from Telegram
    asyncio.run(main_fetch(start_date, end_date))

    # 2. Ingest to raw_pipeline with Anti-Duplicate SSOT
    ingest_exports_to_raw_pipeline()

if __name__ == "__main__":
    main()
