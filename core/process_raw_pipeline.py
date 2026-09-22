"""
BBKitchen Raw Pipeline Normalization & Processing Engine
Ports battle-tested Appscript normalization, WooCommerce category classification,
anti-jebakan sparepart/brand rules, margin guardrails, and strategic price anchoring.
"""

import os
import re
import sys
import json
import time
import sqlite3
import argparse
from datetime import datetime

# Add local path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ai_gateway import AIGateway, load_env

load_env()

LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bbk.db")
JARVIS_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db")
DB_PATH = JARVIS_DB_PATH if os.path.exists(JARVIS_DB_PATH) else LOCAL_DB_PATH

LOCAL_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
JARVIS_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "config")
CONFIG_DIR = JARVIS_CONFIG_DIR if os.path.exists(JARVIS_CONFIG_DIR) else LOCAL_CONFIG_DIR

def load_ssot_configs():
    cat_file = os.path.join(CONFIG_DIR, "categories_ssot.json")
    wh_file = os.path.join(CONFIG_DIR, "warehouses_ssot.json")
    
    cat_ssot = {}
    if os.path.exists(cat_file):
        with open(cat_file, "r", encoding="utf-8") as f:
            cat_ssot = json.load(f)
            
    wh_ssot = {}
    if os.path.exists(wh_file):
        with open(wh_file, "r", encoding="utf-8") as f:
            wh_ssot = json.load(f)
            
    return cat_ssot, wh_ssot

CAT_SSOT, WH_SSOT = load_ssot_configs()
OFFICIAL_SLUGS = set(CAT_SSOT.get("by_slug", {}).keys())

def resolve_warehouse_partner(source_group: str) -> tuple:
    partners = WH_SSOT.get("partners", {})
    sg_str = str(source_group).strip()
    for code, p in partners.items():
        if p.get("telegram_id") and str(p.get("telegram_id")).strip() == sg_str:
            return (p["code"], p["location"])
    # Default fallback to main physical hub (Pamulang 2, Tangsel)
    main_hub = partners.get("GK", {"code": "GK", "location": "PAMULANG 2, TANGSEL"})
    return (main_hub["code"], main_hub["location"])

SYSTEM_PROMPT = """Anda adalah Principal Catalog Architect & Senior Equipment Expert untuk BBKitchen (Penyedia Peralatan Dapur Komersial & Resto Second Terbesar di Indonesia).

Tugas Anda: Menganalisis caption mentah Telegram dari gudang mitra, mengekstrak spesifikasi teknis, menyaring informasi sensitif, dan menghasilkan data katalog standar industri Horeca.

ATURAN BISNIS MUTLAK:
1. JUDUL PRODUK RESMI ("title_bersih"):
   - Format wajib: [Nama Standar Alat] [Brand/Merk] Second [Dimensi/Kapasitas]
   - Contoh ideal:
     * "Upright Chiller 2 Pintu Mastercool Second"
     * "Meja Stainless 2 Susun Second 150x70x85 cm"
     * "Single Sink Stainless 1 Lubang Sayap Kiri Second 100 cm"
     * "Kwali Range 2 Burner Second Blower"
     * "Combi Oven 6 Tray Rational Second"
   - Maksimal 60 karakter, Title Case.
   - JANGAN mengulang nama merk atau kata "Second" dua kali!
   - DILARANG KERAS memuat angka harga, kata "JUAL", "DIJUAL", nomor WhatsApp, atau kata promosi murahan.
   - BRAND & DIMENSI HIERARCHY:
     * Unit Fabrikasi Stainless (Meja, Sink, Rak, Hood, Wallshelf, Kabinet): 99% custom tanpa merk. JANGAN cari merk! UTAMAKAN DIMENSI (PxLxT) & fitur susun/lubang (Contoh: "Meja Stainless 2 Susun Second 150x70x85 cm", "Double Sink Stainless Second 120x60 cm").
     * Unit Mesin, Elektronik & Kompor (Chiller, Freezer, Kwali, Fryer, Oven, Showcase): Jika merk resmi tertera jelas di caption (GEA, Mastercool, Nayati, Getra, Escoffier, Rational), cantumkan merk. Jika merk pudar/tidak ada, JANGAN mengarang merk! Utamakan kapasitas & dimensi (Contoh: "Upright Chiller 2 Pintu Second 120x70x195 cm", "Kwali Range 2 Burner Second Blower").
   - KAMUS SLANG & TYPO FONETIK GUDANG LOKAL:
     * "shocess", "sokes", "sowkes", "chocase" -> Showcase
     * "ciler", "ciller", "aprait", "anderconter" -> Chiller / Upright Chiller / Undercounter Chiller
     * "prizer", "freser", "frizer" -> Freezer / Chest Freezer
     * "sing", "singk", "bak cuci" -> Sink Stainless
     * "kwali bloer", "kuali ren" -> Kwali Range Blower
     * "dip frayer", "preyer gas" -> Deep Fryer
     * "bekples", "beckplash" -> Backsplash
     * "ambalan", "trap", "selping" -> Susun / Undershelf / Overshelf
     * "greastrep", "gris trap" -> Grease Trap
     * "stimer", "kukusan" -> Dimsum Steamer
   - BRAND FILTER: Jangan gunakan kata "Stainless", "Heavy Duty", "Import", "Custom", "Ex Cafe", "Second" sebagai nama merk. Jika tidak bermerk resmi, sebutkan saja jenis bahannya (misal "Meja Stainless 2 Susun Second").

2. CATEGORY SLUG (PILIH 1 SLUG RESMI WOOCOMMERCE YANG PALING TEPAT):
   - CHILLER: "undercounter-chiller", "upright-chiller", "chiller", "lainnya-chiller"
   - FREEZER: "chest-freezer", "upright-freezer", "freezer", "lainnya-freezer"
   - MEJA STAINLESS: "meja-1-susun-stainless", "meja-2-susun-stainless", "meja-3-susun-stainless", "meja-bumbu-stainless", "meja-kabinet-stainless", "meja-kompor-stainless", "meja-stainless", "lainnya-meja-stainless"
   - SINK STAINLESS: "single-sink-stainless", "double-sink-stainless", "triple-sink-stainless", "sink-jumbo-stainless", "sink-stainless", "lainnya-sink"
   - KOMPOR & COOKING: "kompor-1-tungku", "kompor-2-tungku", "kompor-3-tungku", "kompor-4-tungku", "kompor-6-tungku", "kompor-wok-kwali-range", "kompor-batu-lava", "kompor-grill-tepanyaki", "deep-fryer", "noodle-boiler", "oven", "kompor", "lainnya-kompor"
   - RAK STAINLESS: "rak-1-susun-stainless", "rak-2-susun-stainless", "rak-3-susun-stainless", "rak-4-susun-stainless", "rak-5-susun-stainless", "wallshelf", "rak-stainless", "lainnya-rak-stainless"
   - HOOD & VENTILASI: "hood", "blower", "ducting", "hood-stainless", "lainnya-hood"
   - SHOWCASE: "showcase-1-pintu", "showcase-2-pintu", "cake-showcase", "showcase", "lainnya-showcase"
   - ICE SYSTEM: "ice-bin", "ice-maker", "ice-system", "lainnya-ice-system"
   - LAINNYA: "peralatan-dapur-bekas-lainnya"

3. STRATEGIC PRICE ANCHORING:
   - "harga_modal": Angka bulat rupiah modal borongan yang tertulis di caption. Abaikan format titik/koma (misal "12.500.000" -> 12500000, "7,5jt" -> 7500000). Jika tidak disebutkan sama sekali di caption, isi null.
   - "estimasi_harga_baru": Taksiran harga wajar unit BARU dari distributor resmi untuk alat tipe/merk tersebut di Indonesia (dalam angka integer rupiah). Contoh: Chiller 2 pintu baru ~30.000.000, Kwali 2 burner baru ~22.000.000, Deep fryer 1 tank baru ~6.500.000.

4. SEO & KONTEN:
   - "yoast_keyword": "[nama alat] bekas" (contoh: "upright chiller mastercool bekas")
   - "yoast_description": Deskripsi meta menarik max 150 karakter.
   - "spesifikasi_ringkas": Array berisi 4-6 poin spesifikasi teknis penting (dimensi, watt/daya, voltase, kapasitas, kelengkapan).
   - "kondisi_unit": "Bekas Siap Pakai" atau "Like New / Ex-Display" atau "Baru Sisa Proyek"
   - "status_unit": "READY" (Kecuali ada kata LAKU/SOLD/TERJUAL -> "SOLD")

KEMBALIKAN STRICTLY JSON SESUAI STRUKTUR INI:
{
  "title_bersih": str,
  "nama_alat": str,
  "brand": str,
  "dimensi": str,
  "category_slug": str,
  "kondisi_unit": str,
  "status_unit": str,
  "harga_modal": int or null,
  "estimasi_harga_baru": int,
  "yoast_keyword": str,
  "yoast_description": str,
  "spesifikasi_ringkas": [str]
}

"""

def extract_modal_regex(caption: str) -> int:
    """Fallback regex extractor for modal price from caption."""
    patterns = [
        r'(?:harga|hrg|rp|modal|nett|net|bu)\s*[:.\-]?\s*(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3}){1,3})',
        r'(?:rp\.?\s*)(\d{1,3}(?:[.,]\d{3}){1,3})',
        r'(\d+(?:[.,]\d+)?)\s*(?:jt|juta)',
        r'(\d{1,3}(?:[.,]\d{3}))\s*(?:k|rb|ribu)'
    ]
    for pat in patterns:
        m = re.search(pat, caption, re.IGNORECASE)
        if m:
            val_str = m.group(1).replace('.', '').replace(',', '.')
            try:
                num = float(val_str)
                if 'jt' in pat or 'juta' in pat:
                    return int(num * 1_000_000)
                if 'k' in pat or 'rb' in pat or 'ribu' in pat:
                    return int(num * 1_000)
                if num > 50_000:
                    return int(num)
            except Exception:
                continue
    return 0

def calculate_margins_and_anchors(modal: int, estimasi_baru: int):
    """
    Computes private margin guardrails and public price anchor bounds.
    Public low bound: harga_buka_wa (modal is never exposed).
    Public high bound: min(harga_buka_wa * 1.25, estimasi_baru * 0.75).
    """
    if modal <= 0:
        modal = int(estimasi_baru * 0.35) if estimasi_baru > 0 else 5_000_000

    # Margin brackets
    if modal <= 3_000_000:
        m_floor, m_deal, m_buka = 0.45, 0.55, 0.70
    elif modal <= 10_000_000:
        m_floor, m_deal, m_buka = 0.35, 0.45, 0.55
    elif modal <= 30_000_000:
        m_floor, m_deal, m_buka = 0.25, 0.35, 0.45
    else:
        m_floor, m_deal, m_buka = 0.20, 0.28, 0.38

    harga_floor_wa = int(modal * (1 + m_floor))
    harga_deal_wa = int(modal * (1 + m_deal))
    harga_buka_wa = int(modal * (1 + m_buka))

    # Public Display Low (rounded up to clean 100k)
    harga_display_low = ((harga_buka_wa + 99_999) // 100_000) * 100_000

    # Ensure estimasi_baru is dignified
    if estimasi_baru <= harga_display_low:
        estimasi_baru = int(harga_display_low * 1.8)

    # Public Display High: capped below new price (hemat 25-50% guaranteed)
    raw_high = int(harga_display_low * 1.25)
    ceiling = int(estimasi_baru * 0.75)
    harga_display_high = min(raw_high, ceiling)
    if harga_display_high <= harga_display_low:
        harga_display_high = int(harga_display_low * 1.2)
    harga_display_high = ((harga_display_high + 99_999) // 100_000) * 100_000

    return {
        "harga_modal": modal,
        "margin_floor": m_floor,
        "margin_deal": m_deal,
        "harga_floor_wa": harga_floor_wa,
        "harga_deal_wa": harga_deal_wa,
        "harga_buka_wa": harga_buka_wa,
        "status_guardrail": "PASS",
        "estimasi_harga_baru": estimasi_baru,
        "harga_display_low": harga_display_low,
        "harga_display_high": harga_display_high,
    }

def format_rupiah(num: int) -> str:
    return f"Rp {num:,}".replace(",", ".")

def build_full_description(parsed: dict, pricing: dict, location_name: str) -> str:
    nama = parsed.get("nama_alat", "Peralatan Dapur Komersial")
    brand = parsed.get("brand", "")
    specs = parsed.get("spesifikasi_ringkas", [])
    est_baru = pricing["estimasi_harga_baru"]
    disp_low = pricing["harga_display_low"]
    disp_high = pricing["harga_display_high"]

    hemat_min_pct = round((1 - (disp_high / est_baru)) * 100)
    hemat_max_pct = round((1 - (disp_low / est_baru)) * 100)

    spec_items = "".join([f"<li>{s}</li>" for s in specs]) if specs else "<li>Material bodi stainless steel standar komersial.</li><li>Fungsi operasional teruji siap pakai.</li>"

    html = f"""<div class="bbk-product-description">
  <h3>Spesifikasi & Keunggulan Unit</h3>
  <p>Unit <strong>{nama}</strong> ({brand or 'Commercial Grade'}) dalam kondisi prima dan siap langsung dioperasikan untuk kebutuhan dapur restoran, cafe, bakery, atau katering Anda. Seluruh unit di BBKitchen telah melalui proses kurasi ketat dan uji fungsi mekanikal serta elektrikal sebelum ditawarkan.</p>
  <ul>
    {spec_items}
    <li><strong>Lokasi Unit:</strong> {location_name}</li>
    <li><strong>Kondisi:</strong> {parsed.get('kondisi_unit', 'Bekas Siap Pakai')}</li>
  </ul>

  <div class="panduan-anggaran" style="margin-top: 24px; padding: 16px 20px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;">
    <h4 style="margin-top: 0; color: #0f172a; font-weight: 800;">Panduan Anggaran & Estimasi Nilai Pasar</h4>
    <ul style="margin-bottom: 8px;">
      <li><strong>Estimasi Harga Unit Baru (Distributor):</strong> ~{format_rupiah(est_baru)}</li>
      <li><strong>Rentang Penawaran Unit Second BBKitchen:</strong> {format_rupiah(disp_low)} – {format_rupiah(disp_high)}</li>
      <li><strong>Potensi Efisiensi Investasi:</strong> Hemat {hemat_min_pct}% s/d {hemat_max_pct}% dari harga baru</li>
    </ul>
    <p style="font-size: 12px; color: #64748b; margin-bottom: 0;"><em>*Catatan: Penawaran final bergantung pada grade kemulusan fisik, riwayat operasional, kelengkapan aksesoris, dan paket garansi servis. Hubungi konsultan kami untuk cek unit & penawaran terbaik.</em></p>
  </div>
</div>"""
    return html

def process_single_item(gateway: AIGateway, row: dict, dry_run=False) -> dict:
    sku = row["kode_unit"]
    caption = row["caption_raw"] or ""
    source_group = str(row["source_group"] or "")
    lokasi_gudang = row["lokasi_gudang"] or ""

    # Resolve Warehouse
    hub_code, location_name = resolve_warehouse_partner(source_group)
    if lokasi_gudang and any(h in lokasi_gudang for h in ["TANGSEL", "DEPOK", "HQ", "BOGOR"]):
        location_name = lokasi_gudang

    # AI Call
    user_prompt = f"""Caption Mentah Gudang:
\"\"\"{caption}\"\"\"

Ekstrak dan susun data katalog untuk kode unit {sku} sesuai panduan sistem."""
    
    parsed = gateway.generate_json(user_prompt, system_prompt=SYSTEM_PROMPT)

    # Title & Branding (Safe against None values from AI)
    title_bersih = (parsed.get("title_bersih") or "").strip()
    nama_alat = (parsed.get("nama_alat") or "Peralatan Dapur Komersial").strip()
    brand = (parsed.get("brand") or "").strip()
    dimensi = (parsed.get("dimensi") or "").strip()

    if title_bersih:
        title = title_bersih
    else:
        parts = [nama_alat]
        if brand and brand.lower() not in nama_alat.lower():
            parts.append(brand)
        if "second" not in [p.lower() for p in parts]:
            parts.append("Second")
        if dimensi and len(dimensi) <= 15 and dimensi.lower() not in nama_alat.lower():
            parts.append(dimensi)
        title = " ".join(parts)

    # Sanitize title: strip prices, phone numbers, clean multiple spaces
    title = re.sub(r'(?i)(?:rp\.?\s*[\d.,]+|[\d.,]+\s*(?:jt|juta|k|rb|ribu))', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 65:
        title = title[:65].rsplit(" ", 1)[0]

    # Clean Slug
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    link_unit = f"https://bukanbarukitchen.com/shop/{slug}/"


    # Pricing & Anchoring
    modal = parsed.get("harga_modal")
    if not modal or not isinstance(modal, (int, float)) or modal <= 0:
        modal = extract_modal_regex(caption)
    
    est_baru = parsed.get("estimasi_harga_baru")
    if not est_baru or not isinstance(est_baru, (int, float)) or est_baru <= 0:
        est_baru = 15_000_000
    
    pricing = calculate_margins_and_anchors(int(modal), int(est_baru))

    # Descriptions
    short_desc = f"{title} kondisi {parsed.get('kondisi_unit', 'Bekas Siap Pakai')}. Lokasi unit di {location_name}. Lolos inspeksi fungsi dan siap kirim bergaransi."
    full_desc = build_full_description(parsed, pricing, location_name)

    # Categories
    cat_slug = parsed.get("category_slug", "peralatan-dapur-bekas-lainnya")
    if cat_slug not in OFFICIAL_SLUGS:
        cat_slug = "peralatan-dapur-bekas-lainnya"

    # Status
    status_unit = parsed.get("status_unit", "READY").upper()
    if status_unit not in ["READY", "SOLD", "BOOKED", "DP"]:
        status_unit = "READY"

    # Yoast
    yoast_kw = parsed.get("yoast_keyword", f"{nama_alat.lower()} bekas")[:60]
    yoast_desc = parsed.get("yoast_description", short_desc)[:155]

    product_record = {
        "sku": sku,
        "slug": slug,
        "title": title,
        "seo_title": f"{title} | BBKitchen",
        "category_slug": cat_slug,
        "status_unit": status_unit,
        "status_pipeline": "PROCESSED",
        "lokasi_unit": location_name,
        "kondisi_unit": parsed.get("kondisi_unit", "Bekas Siap Pakai"),
        "short_description": short_desc,
        "full_description": full_desc,
        "yoast_keyword": yoast_kw,
        "yoast_description": yoast_desc,
        "featured_image": f"{sku}_1.webp",
        "photo_urls": row["photo_urls"] or f"{sku}_1.webp",
        "tanggal_masuk": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tanggal_terjual": None,
        "durasi_terjual": None,
        "link_telegram": row["link_message"],
        "product_id_woo": None,
        "is_dirty": 1,
        "image_alt": f"{title} - BBKitchen Spesialis Alat Dapur Second",
        "image_title": title,
        "image_caption": f"{title} siap kirim dari {location_name}",
        "image_description": short_desc,
        "asal_gudang": hub_code,
        "harga_modal": pricing["harga_modal"],
        "harga_buka_wa": pricing["harga_buka_wa"],
        "harga_deal_wa": pricing["harga_deal_wa"],
        "harga_floor_wa": pricing["harga_floor_wa"],
        "margin_floor": pricing["margin_floor"],
        "margin_deal": pricing["margin_deal"],
        "status_guardrail": pricing["status_guardrail"],
        "last_checked_telegram": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "link_unit": link_unit,
        "estimasi_harga_baru": pricing["estimasi_harga_baru"],
        "harga_display_low": pricing["harga_display_low"],
        "harga_display_high": pricing["harga_display_high"],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return product_record

def run_pipeline(dry_run=False, limit=None):
    gateway = AIGateway()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Query pending raw units
    query = """
        SELECT kode_unit, source_group, link_message, caption_raw, photo_urls, lokasi_gudang, status_unit
        FROM raw_pipeline
        WHERE kode_unit NOT IN (SELECT sku FROM products)
        ORDER BY CAST(SUBSTR(kode_unit, 4) AS INTEGER) ASC
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = cur.execute(query).fetchall()
    total = len(rows)
    print(f"=== BBKitchen AI Pipeline Ingestion ===")
    print(f"Found {total} pending raw records to process. (Dry-Run: {dry_run})")

    success_count = 0
    fail_count = 0

    for idx, r in enumerate(rows, 1):
        sku = r["kode_unit"]
        print(f"[{idx}/{total}] Processing {sku}...")
        try:
            record = process_single_item(gateway, dict(r), dry_run=dry_run)
            
            print(f"   -> Title: '{record['title']}' ({len(record['title'])} chars)")
            print(f"   -> Category: {record['category_slug']}")
            print(f"   -> Modal: {format_rupiah(record['harga_modal'])} | Buka WA: {format_rupiah(record['harga_buka_wa'])}")
            print(f"   -> Display Range: {format_rupiah(record['harga_display_low'])} - {format_rupiah(record['harga_display_high'])} (Baru: ~{format_rupiah(record['estimasi_harga_baru'])})")
            print(f"   -> Slug: {record['link_unit']}")

            if not dry_run:
                cols = list(record.keys())
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                update_clause = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "sku"])
                
                insert_sql = f"""
                    INSERT INTO products ({col_names})
                    VALUES ({placeholders})
                    ON CONFLICT(sku) DO UPDATE SET {update_clause}
                """
                cur.execute(insert_sql, [record[c] for c in cols])
                cur.execute("UPDATE raw_pipeline SET is_processed = '1' WHERE kode_unit = ?", (sku,))
                conn.commit()

            success_count += 1
            # Polite pause to stay well within provider rate limits
            time.sleep(0.4)

        except Exception as e:
            print(f"   [ERROR] Failed processing {sku}: {e}")
            fail_count += 1

    conn.close()
    print(f"\nPipeline Finished! Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Test run without writing to DB")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to process")
    args = parser.parse_args()

    run_pipeline(dry_run=args.dry_run, limit=args.limit)
