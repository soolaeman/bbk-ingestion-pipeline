# -*- coding: utf-8 -*-
"""
👑 BBKitchen Database Schema & Seed Initializer
Ensures all required tables exist in SQLite (both local and cloud runner),
populates master SSOT tables from JSON configs, and bootstraps anti-duplicate index.
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
    conn.close()

if __name__ == "__main__":
    db_test = ROOT_DIR / "bbk.db"
    ensure_db_schema(db_test)
    print("Schema initialization verified.")
