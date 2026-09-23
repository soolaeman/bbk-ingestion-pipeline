# -*- coding: utf-8 -*-
"""
👑 BBKitchen Database Schema & Seed Initializer
Ensures all required tables exist in SQLite (both local and cloud runner),
populates master SSOT tables from JSON configs, and bootstraps anti-duplicate index from Turso.
"""

import os
import json
import sqlite3
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
CONFIG_DIR = ROOT_DIR / "config"

def ensure_db_schema(db_path):
    """Creates all SSOT tables in SQLite if they don't already exist."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS raw_pipeline (
        kode_unit TEXT PRIMARY KEY,
        source_group TEXT,
        link_message TEXT,
        caption_raw TEXT,
        photo_urls TEXT,
        fetch_date TEXT,
        last_seen_date TEXT,
        lokasi_gudang TEXT,
        status_unit TEXT,
        is_processed TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        title TEXT,
        seo_title TEXT,
        category_slug TEXT,
        status_unit TEXT DEFAULT 'AVAILABLE',
        status_pipeline TEXT,
        lokasi_unit TEXT,
        kondisi_unit TEXT,
        short_description TEXT,
        full_description TEXT,
        yoast_keyword TEXT,
        yoast_description TEXT,
        featured_image TEXT,
        photo_urls TEXT,
        tanggal_masuk TEXT,
        tanggal_terjual TEXT,
        durasi_terjual REAL,
        link_telegram TEXT,
        product_id_woo TEXT,
        is_dirty INTEGER DEFAULT 0,
        image_alt TEXT,
        image_title TEXT,
        image_caption TEXT,
        image_description TEXT,
        asal_gudang TEXT,
        harga_modal REAL,
        harga_buka_wa REAL,
        harga_deal_wa REAL,
        harga_floor_wa REAL,
        margin_floor REAL,
        margin_deal REAL,
        status_guardrail TEXT,
        last_checked_telegram TEXT,
        link_unit TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        estimasi_harga_baru INTEGER,
        harga_display_low INTEGER,
        harga_display_high INTEGER,
        slug TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS master_categories (
        term_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        parent_id INTEGER NOT NULL,
        parent_slug TEXT,
        description TEXT,
        thumbnail TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS master_warehouses (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        hub_id TEXT NOT NULL,
        location TEXT NOT NULL,
        telegram_id TEXT
    )
    """)

    # Populate categories if empty
    cur.execute("SELECT COUNT(*) FROM master_categories")
    if cur.fetchone()[0] == 0:
        cat_file = CONFIG_DIR / "categories_ssot.json"
        if cat_file.exists():
            with open(cat_file, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
                for slug, c in cat_data.get("by_slug", {}).items():
                    cur.execute("""
                    INSERT OR REPLACE INTO master_categories (term_id, name, slug, parent_id, parent_slug, description, thumbnail)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (c.get("term_id", 0), c.get("name", slug), slug, c.get("parent_id", 0), c.get("parent_slug", ""), c.get("description", ""), c.get("thumbnail", "")))

    # Populate warehouses if empty
    cur.execute("SELECT COUNT(*) FROM master_warehouses")
    if cur.fetchone()[0] == 0:
        wh_file = CONFIG_DIR / "warehouses_ssot.json"
        if wh_file.exists():
            with open(wh_file, "r", encoding="utf-8") as f:
                wh_data = json.load(f)
                for code, w in wh_data.get("partners", {}).items():
                    cur.execute("""
                    INSERT OR REPLACE INTO master_warehouses (code, name, hub_id, location, telegram_id)
                    VALUES (?, ?, ?, ?, ?)
                    """, (code, w.get("name", code), w.get("hub_id", code), w.get("location", ""), w.get("telegram_id", "")))

    conn.commit()

    # If products table is empty (fresh cloud runner), bootstrap existing links & max SKU from Turso
    cur.execute("SELECT COUNT(*) FROM products")
    prod_count = cur.fetchone()[0]
    if prod_count == 0:
        bootstrap_from_turso(conn)

    conn.close()

def bootstrap_from_turso(conn):
    """Pulls existing telegram links and max SKU from Turso Cloud Edge to seed the local runner."""
    turso_url = os.getenv("TURSO_DATABASE_URL", "libsql://bbk-soolaeman.aws-ap-northeast-1.turso.io")
    turso_token = os.getenv("TURSO_AUTH_TOKEN", "")
    if not turso_token:
        return

    http_url = turso_url.replace("libsql://", "https://").rstrip("/") + "/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {turso_token}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": "SELECT sku, link_telegram, featured_image FROM products WHERE link_telegram IS NOT NULL AND link_telegram != ''"
                    }
                }
            ]
        }
        res = requests.post(http_url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            rows = data.get("results", [{}])[0].get("response", {}).get("result", {}).get("rows", [])
            cur = conn.cursor()
            inserted = 0
            for r in rows:
                sku = r[0].get("value")
                link_tg = r[1].get("value")
                feat_img = r[2].get("value") if len(r) > 2 else ""
                if sku and link_tg:
                    cur.execute("INSERT OR IGNORE INTO products (sku, link_telegram, featured_image) VALUES (?, ?, ?)", (sku, link_tg, feat_img))
                    inserted += 1
            conn.commit()
            print(f"📥 [CLOUD BOOTSTRAP] Sukses memuat {inserted} link Telegram dari Turso Cloud Edge.")
    except Exception as e:
        print(f"⚠️ [CLOUD BOOTSTRAP WARNING] Gagal menarik link dari Turso: {e}")

if __name__ == "__main__":
    db_test = ROOT_DIR / "bbk.db"
    ensure_db_schema(db_test)
    print("Schema initialization verified.")
