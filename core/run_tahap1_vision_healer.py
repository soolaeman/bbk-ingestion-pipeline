# -*- coding: utf-8 -*-
"""
👑 BBKitchen Sovereign Autonomous Vision Healer & Chef Copywriting Engine (Tahap 1)
Processes all confirmed R2 photos (~1,192 SKUs) via Holver gemini-3.8-flash (Base64).
Performs:
1. Physical visual inspection & 66-Category SSOT calibration.
2. Auto-heal of sequence shift / desync (matching title & category to the true physical photo).
3. Professional Chef Copywriting (4-pilar: Kitchen Station Workflow, Material Durability, QC Report, ROI).
4. Strictly factual (zero hallucination of dimensions/brand; general commercial chef utility when specs sparse).
"""

import os
import sys
import json
import time
import base64
import sqlite3
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
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

load_env()

JARVIS_DB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db"))
CONFIG_CAT_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "config", "categories_ssot.json"))
CACHE_R2_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "r2_uploaded_cache.txt"))
CHECKPOINT_FILE = os.path.join(CURRENT_DIR, "tahap1_checkpoint.json")

HOLVER_KEY = os.getenv("HOLVER_API_KEY", "")
CDN_BASE_URL = "https://bukanbarukitchen.com/api/cdn"
HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
HEADERS_AI = {"Authorization": f"Bearer {HOLVER_KEY}", "Content-Type": "application/json"}

# Load 66 SSOT categories
with open(CONFIG_CAT_PATH, "r", encoding="utf-8") as f:
    CAT_SSOT_DATA = json.load(f)
VALID_SLUGS = list(CAT_SSOT_DATA.get("by_slug", {}).keys())

SYSTEM_PROMPT = f"""Anda adalah Senior Executive Chef & Commercial Kitchen Equipment Forensic Specialist untuk BBKitchen (Pusat Peralatan Dapur Restoran Terbesar di Indonesia).

Tugas Anda: Memeriksa FOTO FISIK ALAT DAPUR ini secara objektif dan menghasilkan metadata serta deskripsi operasional berkelas profesional.

PRINSIP KETAT:
1. FAKTUAL & ZERO HALLUCINATION: Jangan mengarang nomor model, daya watt, atau dimensi jika tidak terlihat di foto atau tidak tertulis di raw text. Jika data minim, jelaskan fungsi operasional komersial umumnya dengan bahasa chef profesional.
2. KALIBRASI VISUAL & KONDISI FISIK: Tentukan nama alat dan kategori SSOT yang PALING SESUAI DENGAN APA YANG TAMPAK DI FOTO FISIK.
   - DETEKSI UNIT BARU VS BEKAS: Periksa apakah permukaan stainless masih terbungkus stiker/lapisan film plastik proteksi pabrik (warna biru, putih, atau bening) atau tampak 100% mulus gress pabrik tanpa jejak noda/baret pemakaian. Jika ya, set "kondisi_unit": "Baru", "estimasi_kondisi_persen": 100, dan beri akhiran 'Baru' pada nama alat. Jika tampak bekas/second, set "kondisi_unit": "Bekas" dan beri akhiran 'Second'.
3. DAFTAR PILIHAN KATEGORI 66-SSOT WAJIB DIPILIH DARI DAFTAR BERIKUT:
{json.dumps(VALID_SLUGS, ensure_ascii=False)}

KEMBALIKAN STRICTLY JSON DENGAN FORMAT:
{{
  "nama_alat_terkalibrasi": "Nama baku alat (misal: 'Meja Kerja Stainless Steel 2 Susun Flat Top Second' atau 'Meja Kerja Stainless Steel 2 Susun Flat Top Baru')",
  "kategori_slug": "<pilih salah satu slug dari 66-SSOT di atas yang paling tepat>",
  "kondisi_unit": "Baru atau Bekas",
  "is_desync": true,
  "estimasi_kondisi_persen": 85,
  "ringkasan_chef": "2-3 kalimat padat berbobot use-case operasional dapur komersial.",
  "rekomendasi_station": "Stasiun alur kerja dapur mana yang paling optimal (Hot Line, Prep Station, Dishwashing, Bakery/Pastry, atau Beverage Bar).",
  "keunggulan_material_higiene": "Durabilitas plat stainless, ketahanan panas/karat, dan kemudahan sanitasi food contact standar HACCP.",
  "catatan_uji_fisik": "Deskripsi faktual penampakan fisik alat, kelurusan bodi, kelengkapan rak/burner/pintu, stiker proteksi pabrik (jika ada), dan jejak pemakaian wajar."
}}
"""

def build_full_html_description(nama: str, cat_slug: str, brand: str, location: str, kondisi: str, chef_data: Dict[str, Any], harga_low: int, harga_high: int, est_baru: int) -> str:
    station = chef_data.get("rekomendasi_station", "Area Preparasi dan Pengolahan Dapur Komersial")
    material = chef_data.get("keunggulan_material_higiene", "Material stainless steel food grade komersial yang higienis, tahan karat, dan mudah disanitasi.")
    catatan_fisik = chef_data.get("catatan_uji_fisik", "Fisik unit terawat, struktur kokoh tanpa deformasi, siap langsung dioperasikan.")
    kondisi_pct = chef_data.get("estimasi_kondisi_persen", 85)
    
    harga_low_str = f"Rp {harga_low:,}".replace(",", ".")
    harga_high_str = f"Rp {harga_high:,}".replace(",", ".")
    est_baru_str = f"Rp {est_baru:,}".replace(",", ".")

    html = f"""<div class="bbk-product-description">
  <div class="chef-recommendation" style="margin-bottom: 20px;">
    <h4 style="color: #0f172a; font-weight: 700; margin-bottom: 8px;">👨‍🍳 Rekomendasi Stasiun Dapur & Alur Operasional</h4>
    <p style="color: #334155; line-height: 1.6; margin: 0;">{station}</p>
  </div>

  <div class="material-durability" style="margin-bottom: 20px;">
    <h4 style="color: #0f172a; font-weight: 700; margin-bottom: 8px;">🛡️ Standar Material & Durabilitas Higienis</h4>
    <p style="color: #334155; line-height: 1.6; margin: 0;">{material}</p>
  </div>

  <div class="qc-inspection" style="margin-bottom: 20px;">
    <h4 style="color: #0f172a; font-weight: 700; margin-bottom: 8px;">⚙️ Catatan Uji Fungsi & Fisik Teknisi BBKitchen</h4>
    <ul style="color: #334155; line-height: 1.6; padding-left: 20px; margin: 0;">
      <li><strong>Estimasi Fisik:</strong> Sekitar {kondisi_pct}% ({catatan_fisik})</li>
      <li><strong>Lokasi Unit:</strong> {location}</li>
      <li><strong>Kondisi:</strong> {kondisi}</li>
      <li><strong>Jaminan & Garansi:</strong> Garansi Servis 14 Hari BBKitchen & Lolos Uji Fungsi Siap Pakai</li>
    </ul>
  </div>

  <div class="panduan-anggaran" style="padding: 16px 20px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;">
    <h4 style="margin-top: 0; color: #0f172a; font-weight: 800;">Panduan Anggaran & Estimasi Nilai Pasar</h4>
    <ul style="margin-bottom: 8px; color: #334155; line-height: 1.6; padding-left: 20px;">
      <li><strong>Estimasi Harga Unit Baru (Distributor):</strong> ~{est_baru_str}</li>
      <li><strong>Rentang Penawaran Unit Second BBKitchen:</strong> {harga_low_str} - {harga_high_str}</li>
      <li><strong>Efisiensi Investasi:</strong> Hemat signifikan dibanding beli baru dengan fungsi operasional setara</li>
    </ul>
    <p style="font-size: 12px; color: #64748b; margin-bottom: 0;"><em>*Catatan: Penawaran final bergantung pada grade kemulusan fisik, kelengkapan aksesoris, dan paket garansi servis. Hubungi konsultan kami untuk cek unit & video tes.</em></p>
  </div>
</div>"""
    return html

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_http_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS_WEB)
    return session

HTTP_SESSION = get_http_session()

def process_single_sku(row_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sku = row_data["sku"]
    curr_title = row_data["title"]
    curr_cat = row_data["category_slug"] or ""
    brand = row_data.get("brand", "")
    location = row_data.get("lokasi_unit", "Gudang Pusat BBKitchen")
    kondisi = row_data.get("kondisi_unit", "Bekas Siap Pakai")
    harga_low = int(row_data.get("harga_display_low") or 0)
    harga_high = int(row_data.get("harga_display_high") or 0)
    est_baru = int(row_data.get("estimasi_harga_baru") or 10_000_000)
    
    photo_filename = f"{sku}_1.webp"
    img_url = f"{CDN_BASE_URL}/{photo_filename}"
    
    # 1. Download image from CDN with session
    try:
        r_img = HTTP_SESSION.get(img_url, timeout=20)
        if r_img.status_code != 200 or len(r_img.content) < 1000:
            return {
                "sku": sku,
                "status": "SKIP_NO_CDN_IMAGE",
                "error": f"CDN returned {r_img.status_code}"
            }
        
        b64_str = base64.b64encode(r_img.content).decode("utf-8")
        data_url = f"data:image/webp;base64,{b64_str}"
    except Exception as e:
        return {"sku": sku, "status": "ERR_IMAGE_DOWNLOAD", "error": str(e)}

    # 2. Call Holver gemini-3.8-flash with 429 Exponential Backoff
    full_prompt = f"""{SYSTEM_PROMPT}

Data saat ini di database:
- SKU: "{sku}"
- Judul Saat Ini: "{curr_title}"
- Kategori Slug Saat Ini: "{curr_cat}"
- Lokasi Unit: "{location}"
- Kondisi Unit: "{kondisi}"

Periksa FOTO FISIK unit {sku} ini. Tentukan nama baku alat, kategori 66-SSOT yang benar, evaluasi apakah desync, dan susun copywriting Chef profesional yang faktual."""

    payload = {
        "model": "gemini-3.8-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": full_prompt},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    max_attempts = 5
    ai_res = None
    for attempt in range(max_attempts):
        try:
            ai_res = requests.post("https://api.holver.id/v1/chat/completions", headers=HEADERS_AI, json=payload, timeout=45)
            if ai_res.status_code == 200:
                break
            elif ai_res.status_code == 429:
                wait_sec = 6 * (attempt + 1)
                time.sleep(wait_sec)
            else:
                time.sleep(2)
        except Exception:
            time.sleep(3)

    if not ai_res or ai_res.status_code != 200:
        err_detail = ai_res.text[:100] if ai_res else "No response"
        return {"sku": sku, "status": "ERR_AI_API", "error": f"HTTP {ai_res.status_code if ai_res else 'NONE'}: {err_detail}"}

    try:
        raw_content = ai_res.json()["choices"][0]["message"]["content"]
        if "```" in raw_content:
            raw_content = raw_content.split("```")[1].replace("json", "").strip()
            
        import re
        try:
            data = json.loads(raw_content)
        except Exception:
            m = re.search(r"(\{.*\})", raw_content, re.DOTALL)
            if m:
                data = json.loads(m.group(1))
            else:
                return {"sku": sku, "status": "ERR_JSON_PARSE", "error": f"Raw content: {raw_content[:80]}"}
        
        new_title = data.get("nama_alat_terkalibrasi") or curr_title
        new_cat = data.get("kategori_slug") or curr_cat
        if new_cat not in VALID_SLUGS:
            new_cat = curr_cat if curr_cat in VALID_SLUGS else "peralatan-dapur-bekas-lainnya"
            
        is_desync = bool(data.get("is_desync", False) or (new_cat != curr_cat))
        kondisi_pct = int(data.get("estimasi_kondisi_persen") or 85)
        ringkasan = data.get("ringkasan_chef") or f"{new_title} kondisi {kondisi} siap pakai untuk operasional dapur komersial."
        
        new_kondisi = data.get("kondisi_unit") or kondisi
        if "baru" in str(new_kondisi).lower():
            new_kondisi = "Baru"
        else:
            new_kondisi = "Bekas"

        full_html = build_full_html_description(
            nama=new_title,
            cat_slug=new_cat,
            brand=brand,
            location=location,
            kondisi=new_kondisi,
            chef_data=data,
            harga_low=harga_low,
            harga_high=harga_high,
            est_baru=est_baru
        )
        
        desync_flag = 1 if is_desync else 0
        vision_status = "DESYNC_HEALED" if is_desync else "VERIFIED_MATCH"
        reconcile_log = f"TAHAP1_HEAL: OldCat={curr_cat} -> NewCat={new_cat} | Match={not is_desync} | Kondisi={new_kondisi}"
        
        return {
            "sku": sku,
            "status": "SUCCESS",
            "new_title": new_title,
            "new_cat": new_cat,
            "new_kondisi": new_kondisi,
            "is_desync": is_desync,
            "desync_flag": desync_flag,
            "vision_status": vision_status,
            "kondisi_pct": kondisi_pct,
            "ringkasan": ringkasan,
            "full_html": full_html,
            "reconcile_log": reconcile_log,
            "catatan_fisik": data.get("catatan_uji_fisik", ""),
            "old_title": curr_title,
            "old_cat": curr_cat
        }
    except Exception as e:
        return {"sku": sku, "status": "ERR_PROCESSING", "error": str(e)}

def update_product_in_db(res: Dict[str, Any]) -> bool:
    max_retries = 5
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(JARVIS_DB_PATH, timeout=30.0, isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("""
                UPDATE products
                SET title = ?,
                    seo_title = ?,
                    category_slug = ?,
                    kondisi_unit = ?,
                    short_description = ?,
                    full_description = ?,
                    ai_vision_status = ?,
                    vision_kategori_slug = ?,
                    vision_fitur_utama = ?,
                    vision_kondisi_persen = ?,
                    vision_catatan = ?,
                    photo_desync_flag = ?,
                    reconciliation_log = ?,
                    updated_at = datetime('now', 'localtime')
                WHERE sku = ?
            """, (
                res["new_title"],
                f"{res['new_title']} | BBKitchen",
                res["new_cat"],
                res["new_kondisi"],
                res["ringkasan"],
                res["full_html"],
                res["vision_status"],
                res["new_cat"],
                json.dumps([res.get("catatan_fisik", "")]),
                res["kondisi_pct"],
                res.get("catatan_fisik", ""),
                res["desync_flag"],
                res["reconcile_log"],
                res["sku"]
            ))
            conn.close()
            return True
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                time.sleep(0.5 * (attempt + 1))
            else:
                raise
        except Exception:
            time.sleep(0.5)
    return False

def run_tahap1_execution(limit: Optional[int] = None, delay: float = 5.0, reset: bool = False):
    print("=" * 68)
    print("👑 BBKITCHEN TAHAP 1: AUTONOMOUS VISION HEALER & CHEF ENGINE")
    print(f"Database Target : {JARVIS_DB_PATH}")
    print(f"Provider AI     : Holver gemini-3.8-flash (Base64 Multimodal)")
    print(f"Pacing Cadence  : {delay}s delay per unit (~{60/delay:.1f} RPM safe limit)")
    print("=" * 68)

    # 1. Load confirmed R2 uploaded cache
    with open(CACHE_R2_PATH, "r", encoding="utf-8") as f:
        r2_cache_keys = set(line.strip() for line in f if line.strip())

    # Reset checkpoint if requested
    if reset and os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("🔄 Checkpoint di-reset dari awal!")

    # Load checkpoint
    processed_skus = set()
    checkpoint_data = {"completed": [], "desync_healed": 0, "verified_match": 0, "errors": 0}
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                checkpoint_data = json.load(f)
                processed_skus = set(checkpoint_data.get("completed", []))
        except Exception:
            pass

    # Read all rows and immediately close connection
    conn_read = sqlite3.connect(JARVIS_DB_PATH, timeout=30.0)
    conn_read.row_factory = sqlite3.Row
    rows = conn_read.execute("SELECT * FROM products ORDER BY CAST(SUBSTR(sku, 4) AS INTEGER) DESC").fetchall()
    all_products = [dict(r) for r in rows]
    conn_read.close()
    
    # Filter products confirmed in R2 (Instant O(1) set lookup)
    r2_sku_set = set(k.split('_')[0] for k in r2_cache_keys if '_' in k)
    eligible_rows = [r for r in all_products if r["sku"] in r2_sku_set]

    pending_rows = [r for r in eligible_rows if r["sku"] not in processed_skus]
    if limit:
        pending_rows = pending_rows[:limit]

    total_target = len(eligible_rows)
    print(f"📋 Total Unit Berfoto di R2 : {total_target}")
    print(f"✅ Sudah Selesai Sebelumnya : {len(processed_skus)}")
    print(f"⚡ Antrean yang Akan Dijalankan: {len(pending_rows)}")
    print("-" * 68)

    if not pending_rows:
        print("🎉 Semua unit berfoto di R2 sudah selesai diproses!")
        return

    start_time = time.time()
    completed_in_session = 0
    desync_count = checkpoint_data.get("desync_healed", 0)
    match_count = checkpoint_data.get("verified_match", 0)

    for row in pending_rows:
        sku = row["sku"]
        res = process_single_sku(row)
        completed_in_session += 1
        curr_done = len(processed_skus) + 1
        
        # Progress calculation
        pct = (curr_done / total_target) * 100
        elapsed = time.time() - start_time
        sec_per_unit = elapsed / completed_in_session if completed_in_session > 0 else delay
        rem_units = total_target - curr_done
        rem_min = (rem_units * sec_per_unit) / 60
        
        bar_len = 12
        filled = int(bar_len * curr_done // total_target)
        bar = "█" * filled + "░" * (bar_len - filled)

        if res and res.get("status") == "SUCCESS":
            processed_skus.add(sku)
            is_desync = res["is_desync"]
            if is_desync:
                desync_count += 1
            else:
                match_count += 1

            # Update SQLite master with atomic retry
            db_ok = update_product_in_db(res)
            if not db_ok:
                print(f"⚠️ Warning: Gagal update DB untuk {sku} setelah retry.")

            tag = "🔴 HEALED DESYNC" if is_desync else "🟢 MATCH"
            new_info = f"[{res['new_cat']}] {res['new_title'][:30]}..."
            print(f"⚡ [{bar}] {pct:.1f}% ({curr_done}/{total_target}) • ETA: ~{rem_min:.0f}m • {sku} ({tag}) -> {new_info}")
            if is_desync:
                old_info = f"[{res['old_cat']}] {res['old_title'][:25]}..."
                print(f"   ↳ Koreksi: {old_info} ➔ {new_info}")
        else:
            err_msg = res.get("error", "Unknown error") if res else "None response"
            print(f"⚡ [{bar}] {pct:.1f}% ({curr_done}/{total_target}) • {sku} (⚠️ {res.get('status', 'ERR') if res else 'ERR'}) -> {err_msg}")

        # Update checkpoint on every item for maximum safety
        checkpoint_data = {
            "completed": list(processed_skus),
            "desync_healed": desync_count,
            "verified_match": match_count,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)

        # Rate limiter sleep
        time.sleep(delay)

    elapsed = time.time() - start_time
    print("=" * 68)
    print(f"🏁 TAHAP 1 SELESAI DALAM {elapsed/60:.1f} MENIT!")
    print(f"✅ Total Terinspeksi : {len(processed_skus)}")
    print(f"🟢 Verified Match    : {match_count}")
    print(f"🔴 Auto-Healed Desync: {desync_count}")
    print("=" * 68)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Tahap 1 Vision Healer")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to test")
    parser.add_argument("--delay", type=float, default=4.5, help="Pacing delay in seconds (default 4.5s)")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint and start from beginning")
    args = parser.parse_args()
    
    run_tahap1_execution(limit=args.limit, delay=args.delay, reset=args.reset)
