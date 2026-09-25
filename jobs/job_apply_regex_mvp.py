# -*- coding: utf-8 -*-
"""
👑 BBKitchen Batch Apply Regex MVP & Human Decisions to SSOT Database (bbk.db)
Applies the deterministic Layer 1 Regex Normalizer + 24 Human Review Decisions
across all 3,147 raw catalog items into SQLite SSOT products table atomically.
"""

import os
import re
import sys
import json
import sqlite3
import time
from typing import Dict, Any, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "..", "core")
for p in [BASE_DIR, CORE_DIR]:
    if p not in sys.path:
        sys.path.append(p)

from normalize_engine import (
    sanitize_raw_caption,
    extract_modal_regex,
    evaluate_condition_binary,
    resolve_warehouse_partner,
    calculate_margins_and_anchors,
    build_rich_description,
    format_rupiah,
    KNOWN_COMMERCIAL_BRANDS,
    FABRICATION_KEYWORDS,
    OFFICIAL_CATEGORY_SLUGS,
    CATEGORY_SYNONYM_MAP,
)
from job_audit_regex_mvp import parse_regex_mvp

DB_PATH = os.path.join(BASE_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db")
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, "..", "bbk.db")

# 24 Human Review Decisions SSOT
HUMAN_DECISIONS_OVERRIDE = {
    "BBK0036": {
        "action": "PUBLISH",
        "title": "Patung Seni Hiasan Abstrak Empat Penjuru Angin T103cm by Ary Sutarya Second",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK0282": {"action": "SKIP_NON_PRODUCT"},
    "BBK0793": {
        "action": "PUBLISH",
        "title": "Lemari Loker 9 Pintu Krisbow & Informa Second 115x50x185 cm",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK0823": {"action": "SKIP_NON_PRODUCT"},
    "BBK0834": {
        "action": "PUBLISH",
        "title": "Lemari Loker 9 Pintu Krisbow Second 115x50x185 cm",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK0874": {"action": "SKIP_NON_PRODUCT"},
    "BBK1235": {"action": "SKIP_NON_PRODUCT"},
    "BBK1309": {"action": "SKIP_NON_PRODUCT"},
    "BBK1405": {
        "action": "PUBLISH",
        "title": "Mesin Fotocopy Fuji Xerox DB132 Second",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK1434": {"action": "SKIP_NON_PRODUCT"},
    "BBK1439": {
        "action": "PUBLISH",
        "title": "Cermin Dinding Komersial Second 50x100 cm",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK1468": {"action": "SKIP_NON_PRODUCT"},
    "BBK1498": {"action": "SKIP_NON_PRODUCT"},
    "BBK1519": {"action": "SKIP_NON_PRODUCT"},
    "BBK1588": {"action": "SKIP_NON_PRODUCT"},
    "BBK1623": {"action": "SKIP_NON_PRODUCT"},
    "BBK1909": {"action": "SKIP_NON_PRODUCT"},
    "BBK2501": {"action": "SKIP_NON_PRODUCT"},
    "BBK2666": {
        "action": "PUBLISH",
        "title": "Kipas Angin Standing Sekai IST 3040 30 inch Second",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK2695": {
        "action": "PUBLISH",
        "title": "Autoclave Sterilisasi Medis GEA YX 18 LDJ Second",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK2795": {"action": "SKIP_NON_PRODUCT"},
    "BBK2980": {
        "action": "PUBLISH",
        "title": "Lemari Loker 9 Pintu Informa Second 115x50x185 cm",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK3054": {
        "action": "PUBLISH",
        "title": "Box Panel Listrik Exhaust & Fresh Air 3 Phase Second 40x22x60 cm",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
    "BBK3055": {
        "action": "PUBLISH",
        "title": "Box Panel Listrik 3 Phase Second 50x22x70 cm",
        "category_slug": "peralatan-dapur-bekas-lainnya",
        "kondisi_tag": "Second",
        "kondisi_unit": "Bekas Siap Pakai",
    },
}

def apply_ssot_batch():
    print(f"=== BBKitchen Batch Applying Regex MVP to SSOT Database ===")
    print(f"Database Target: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Fetch existing products for sacred slug lock
    existing_products = cur.execute("SELECT sku, slug, title FROM products").fetchall()
    slug_map = {r["sku"]: r["slug"] for r in existing_products if r["slug"]}

    # 2. Fetch all raw pipeline items
    raw_rows = cur.execute("SELECT kode_unit, source_group, caption_raw, link_message FROM raw_pipeline ORDER BY CAST(SUBSTR(kode_unit, 4) AS INTEGER) ASC").fetchall()
    total_raw = len(raw_rows)
    print(f"Total Raw Items to Process: {total_raw}")

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    applied_count = 0
    skipped_count = 0

    for r in raw_rows:
        sku = r["kode_unit"]
        caption = r["caption_raw"] or ""
        source_grp = r["source_group"] or ""
        link_msg = r["link_message"] or ""
        existing_slug = slug_map.get(sku)

        # Check Human Override
        if sku in HUMAN_DECISIONS_OVERRIDE:
            dec = HUMAN_DECISIONS_OVERRIDE[sku]
            if dec["action"] == "SKIP_NON_PRODUCT":
                cur.execute("UPDATE raw_pipeline SET status_pipeline = 'SKIP_NON_PRODUCT' WHERE kode_unit = ?", (sku,))
                cur.execute("UPDATE products SET status_pipeline = 'SKIP_NON_PRODUCT', is_dirty = 0, updated_at = ? WHERE sku = ?", (now_str, sku))
                skipped_count += 1
                continue
            else:
                # Custom Publish
                parsed = parse_regex_mvp(caption, sku, existing_slug=existing_slug, source_group=source_grp, link_msg=link_msg)
                parsed["title"] = dec.get("title", parsed["title"])
                parsed["category_slug"] = dec.get("category_slug", parsed["category_slug"])
                parsed["kondisi_tag"] = dec.get("kondisi_tag", parsed["kondisi_tag"])
                parsed["kondisi_unit"] = dec.get("kondisi_unit", parsed["kondisi_unit"])
                parsed["is_non_product"] = False
        else:
            parsed = parse_regex_mvp(caption, sku, existing_slug=existing_slug, source_group=source_grp, link_msg=link_msg)

        if parsed["is_non_product"]:
            cur.execute("UPDATE raw_pipeline SET status_pipeline = 'SKIP_NON_PRODUCT' WHERE kode_unit = ?", (sku,))
            cur.execute("UPDATE products SET status_pipeline = 'SKIP_NON_PRODUCT', is_dirty = 0, updated_at = ? WHERE sku = ?", (now_str, sku))
            skipped_count += 1
            continue

        # Resolve Warehouse
        hub_code, location_name = resolve_warehouse_partner(source_grp, link=link_msg)

        # Margins and Pricing
        pricing = calculate_margins_and_anchors(parsed["harga_modal"], None, category_slug=parsed["category_slug"])

        # Descriptions
        short_desc = f"{parsed['title']} kondisi {parsed['kondisi_unit']}. Lokasi unit di {location_name}. Lolos uji fungsi & siap kirim bergaransi."
        full_desc = build_rich_description(parsed, pricing, location_name, sub_components_baru=parsed["sub_komponen_baru"])
        yoast_kw = f"{parsed['nama_alat'].lower()} bekas"[:60]
        yoast_desc = short_desc[:155]
        link_unit = f"https://bukanbarukitchen.com/shop/{parsed['slug']}/"
        featured_img = f"{sku}_1.webp"

        # Spesifikasi Ringkas JSON
        specs = [
            f"Dimensi: {parsed['dimensi'] or 'Standar Komersial'}",
            "Material stainless steel food grade",
            "Fungsi mekanikal & elektrikal teruji siap pakai",
            "Unit lolos inspeksi quality control BBKitchen"
        ]
        if parsed["sub_komponen_baru"]:
            for sc in parsed["sub_komponen_baru"]:
                specs.insert(0, f"Komponen Refurbished: {sc} (Kondisi Prima)")

        # Upsert into products table
        cur.execute("""
            INSERT INTO products (
                sku, slug, title, seo_title, category_slug, status_unit, status_pipeline,
                lokasi_unit, kondisi_unit, short_description, full_description,
                yoast_keyword, yoast_description, featured_image, photo_urls,
                link_telegram, link_unit, asal_gudang, harga_modal,
                harga_buka_wa, harga_deal_wa, harga_floor_wa, margin_floor, margin_deal,
                status_guardrail, estimasi_harga_baru, harga_display_low, harga_display_high,
                image_alt, image_title, image_caption, image_description,
                is_dirty, normalization_source, spesifikasi_ringkas, ai_enrich_status,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                0, 'REGEX_MVP', ?, 'PENDING',
                ?, ?
            )
            ON CONFLICT(sku) DO UPDATE SET
                slug = excluded.slug,
                title = excluded.title,
                seo_title = excluded.seo_title,
                category_slug = excluded.category_slug,
                status_unit = excluded.status_unit,
                status_pipeline = excluded.status_pipeline,
                lokasi_unit = excluded.lokasi_unit,
                kondisi_unit = excluded.kondisi_unit,
                short_description = excluded.short_description,
                full_description = excluded.full_description,
                yoast_keyword = excluded.yoast_keyword,
                yoast_description = excluded.yoast_description,
                featured_image = excluded.featured_image,
                photo_urls = excluded.photo_urls,
                link_telegram = excluded.link_telegram,
                link_unit = excluded.link_unit,
                asal_gudang = excluded.asal_gudang,
                harga_modal = excluded.harga_modal,
                harga_buka_wa = excluded.harga_buka_wa,
                harga_deal_wa = excluded.harga_deal_wa,
                harga_floor_wa = excluded.harga_floor_wa,
                margin_floor = excluded.margin_floor,
                margin_deal = excluded.margin_deal,
                status_guardrail = excluded.status_guardrail,
                estimasi_harga_baru = excluded.estimasi_harga_baru,
                harga_display_low = excluded.harga_display_low,
                harga_display_high = excluded.harga_display_high,
                image_alt = excluded.image_alt,
                image_title = excluded.image_title,
                image_caption = excluded.image_caption,
                image_description = excluded.image_description,
                is_dirty = 0,
                normalization_source = 'REGEX_MVP',
                spesifikasi_ringkas = excluded.spesifikasi_ringkas,
                updated_at = excluded.updated_at
        """, (
            sku, parsed["slug"], parsed["title"], f"{parsed['title']} | BBKitchen", parsed["category_slug"],
            parsed["status_unit"], "PROCESSED", location_name, parsed["kondisi_unit"], short_desc, full_desc,
            yoast_kw, yoast_desc, featured_img, featured_img, link_msg, link_unit, hub_code,
            pricing["harga_modal"], pricing["harga_buka_wa"], pricing["harga_deal_wa"], pricing["harga_floor_wa"],
            pricing["margin_floor"], pricing["margin_deal"], pricing["status_guardrail"],
            pricing["estimasi_harga_baru"], pricing["harga_display_low"], pricing["harga_display_high"],
            f"{parsed['title']} - BBKitchen Spesialis Alat Dapur Second", parsed["title"],
            f"{parsed['title']} siap kirim dari {location_name}", short_desc,
            json.dumps(specs, ensure_ascii=False), now_str, now_str
        ))

        cur.execute("UPDATE raw_pipeline SET status_pipeline = 'PROCESSED' WHERE kode_unit = ?", (sku,))
        applied_count += 1

    conn.commit()

    # Verification of Twin Slugs (BBK3194 vs BBK3195)
    twin_check = cur.execute("SELECT sku, title, slug FROM products WHERE sku IN ('BBK3194', 'BBK3195')").fetchall()

    conn.close()

    print(f"\n✅ SSOT Batch Apply Completed Successfully!")
    print(f"Total Valid Processed & Published : {applied_count} SKUs")
    print(f"Total Skipped (Non-Product/Chat)  : {skipped_count} SKUs")
    print("\n--- Twin Slug Verification (BBK3194 vs BBK3195) ---")
    for r in twin_check:
        print(f"[{r['sku']}] Title: {r['title']} | Slug: {r['slug']}")

if __name__ == "__main__":
    apply_ssot_batch()
