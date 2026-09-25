"""
BBKitchen Warehouse & Location SSOT Data Healer
Scans all products and raw_pipeline records, detects any mismatched asal_gudang or lokasi_unit
by cross-referencing Telegram link IDs with warehouses_ssot.json, and fixes them in SQLite and Turso.
"""

import os
import sys
import json
import sqlite3

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from ai_gateway import load_env
from sync_turso import get_turso_endpoint, get_headers

load_env()

LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bbk.db")
JARVIS_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db")
DB_PATH = JARVIS_DB_PATH if os.path.exists(JARVIS_DB_PATH) else LOCAL_DB_PATH

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
WH_FILE = os.path.join(CONFIG_DIR, "warehouses_ssot.json")

def heal_all():
    print("=======================================================")
    print("🏥 BBKitchen Warehouse & Location Data Healer")
    print(f"Target DB: {DB_PATH}")
    print("=======================================================")

    with open(WH_FILE, "r", encoding="utf-8") as f:
        wh_data = json.load(f)
    partners = wh_data.get("partners", {})

    # Map cleaned telegram channel ID -> (partner_code, location_name)
    tele_map = {}
    for code, p in partners.items():
        tele_id = str(p.get("telegram_id") or "").strip()
        if tele_id:
            clean_id = tele_id.replace("-100", "").replace("-", "")
            tele_map[clean_id] = (code, p.get("location", "PAMULANG 2, TANGSEL"))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Check and heal products
    prod_rows = cur.execute("SELECT sku, asal_gudang, lokasi_unit, link_telegram, short_description, full_description, image_caption FROM products WHERE link_telegram IS NOT NULL AND link_telegram != ''").fetchall()
    
    fixed_products = []
    for r in prod_rows:
        sku = r["sku"]
        ag = r["asal_gudang"] or ""
        loc = r["lokasi_unit"] or ""
        link = r["link_telegram"] or ""

        for clean_id, (true_code, true_loc) in tele_map.items():
            if f"/c/{clean_id}/" in link or f"/{clean_id}/" in link:
                if ag != true_code or loc != true_loc:
                    # Fix description & caption text if they reference old location
                    short_desc = (r["short_description"] or "").replace(loc, true_loc) if loc else r["short_description"]
                    full_desc = (r["full_description"] or "").replace(loc, true_loc) if loc else r["full_description"]
                    img_cap = (r["image_caption"] or "").replace(loc, true_loc) if loc else r["image_caption"]

                    cur.execute("""
                        UPDATE products
                        SET asal_gudang = ?,
                            lokasi_unit = ?,
                            short_description = ?,
                            full_description = ?,
                            image_caption = ?,
                            is_dirty = 1,
                            updated_at = datetime('now', 'localtime')
                        WHERE sku = ?
                    """, (true_code, true_loc, short_desc, full_desc, img_cap, sku))

                    fixed_products.append((sku, ag, true_code, loc, true_loc))
                break

    conn.commit()
    print(f"✅ Local SQLite Products Healed: {len(fixed_products)} records fixed.")
    for sku, old_ag, new_ag, old_loc, new_loc in fixed_products:
        print(f"  * {sku}: asal_gudang '{old_ag}' -> '{new_ag}' | lokasi '{old_loc}' -> '{new_loc}'")

    # 2. Check and heal raw_pipeline
    raw_rows = cur.execute("SELECT kode_unit, source_group, lokasi_gudang, link_message FROM raw_pipeline WHERE link_message IS NOT NULL AND link_message != ''").fetchall()
    fixed_raw = []
    for r in raw_rows:
        sku = r["kode_unit"]
        sg = r["source_group"] or ""
        loc = r["lokasi_gudang"] or ""
        link = r["link_message"] or ""

        for clean_id, (true_code, true_loc) in tele_map.items():
            if f"/c/{clean_id}/" in link or f"/{clean_id}/" in link:
                if sg != true_code or loc != true_loc:
                    cur.execute("""
                        UPDATE raw_pipeline
                        SET source_group = ?,
                            lokasi_gudang = ?
                        WHERE kode_unit = ?
                    """, (true_code, true_loc, sku))
                    fixed_raw.append((sku, sg, true_code, loc, true_loc))
                break

    conn.commit()
    print(f"✅ Local SQLite raw_pipeline Healed: {len(fixed_raw)} records fixed.")

    conn.close()

    # 3. Sync all fixed products to Turso Edge DB
    if fixed_products:
        print("\n☁️ Syncing healed records to Turso Cloud Edge...")
        from sync_turso import sync_to_turso
        sync_to_turso(only_dirty=True)
        print("🎉 Turso Edge DB successfully synced and healed!")
    else:
        print("\n✨ All records were already clean and matched!")

if __name__ == "__main__":
    heal_all()
