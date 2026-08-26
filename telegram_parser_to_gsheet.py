# -*- coding: utf-8 -*-

import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import gspread
from google.oauth2.service_account import Credentials
from PIL import Image
from requests.exceptions import ReadTimeout  # Ditambahkan untuk menangkap error timeout jaringan
from tqdm import tqdm

# =========================================================
# KONFIGURASI (Jalur Langsung ke Folder Master)
# =========================================================
# Base directory is the folder containing this script (relative)
BASE_DIR = Path(__file__).parent
EXPORT_ROOT = BASE_DIR / "exports"

# Output folder for WebP master (adjust as needed)
OUTPUT_DIR = BASE_DIR.parent / "BBK_WEBP_MASTER"
IMG_DIR = OUTPUT_DIR 

LOGO_FILE = BASE_DIR / "logo.png"
LOGO_SIZE_PERCENT = 0.50
LOGO_OPACITY = 200

MAX_PHOTOS = 999
MAX_SIDE = 1600
WEBP_QUALITY = 80
PHOTO_URL_PREFIX = ""
TIME_WINDOW = 15

SERVICE_ACCOUNT_FILE = BASE_DIR / "credentials.json"
SPREADSHEET_NAME = "BBK_MASTER_SYSTEM"
WORKSHEET_NAME = "RAW_INVENTORY"

LOCAL_TZ = ZoneInfo("Asia/Jakarta")

WAREHOUSE_MAP = {
    "GK": "PAMULANG 2, TANGSEL", "BB": "PAMULANG 2, TANGSEL",
    "SM": "PAMULANG 2, TANGSEL", "BL": "PAMULANG 2, TANGSEL",
    "ML": "PAMULANG BARAT, TANGSEL", "PY": "SETU, TANGSEL",
    "PE": "SAWANGAN, DEPOK", "WT": "KEDAUNG, TANGSEL",
    "ON": "KEDAUNG, TANGSEL", "RB": "PAMULANG BARAT, TANGSEL",
}

SOURCE_MAP = {
    "GK": "https://t.me/c/2479885293", "BB": "https://t.me/c/1947492349",
    "SM": "https://t.me/c/2249769366", "BL": "https://t.me/c/2221612633",
    "ML": "https://t.me/c/2295735681", "PY": "https://t.me/c/2556966592",
    "PE": "https://t.me/c/2471308578", "WT": "https://t.me/c/2559367434",
    "ON": "https://t.me/c/3420173563", "RB": "https://t.me/c/2405866006",
}

# --- Fungsi utama untuk koneksi dan pemrosesan ---
def connect_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    
    # Set timeout global gspread menjadi 60 detik agar koneksi tidak gampang putus
    client.timeout = 60 
    
    return client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)

def resize_and_compress_webp(src, dest):
    try:
        img = Image.open(src).convert("RGB")
        w, h = img.size
        scale = min(MAX_SIDE / max(w, h), 1.0)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            w, h = img.size
        if LOGO_FILE.exists():
            logo_raw = Image.open(LOGO_FILE).convert("RGBA")
            target_w = int(w * LOGO_SIZE_PERCENT)
            logo_h = int(logo_raw.size[1] * (target_w / logo_raw.size[0]))
            logo = logo_raw.resize((target_w, logo_h), Image.LANCZOS)
            alpha = logo.getchannel("A").point(lambda i: int(i * LOGO_OPACITY / 255))
            logo.putalpha(alpha)
            img_rgba = img.convert("RGBA")
            x, y = (w - target_w) // 2, int(h * 0.03)
            img_rgba.paste(logo, (x, y), logo)
            img = img_rgba.convert("RGB")
        img.save(dest, "WEBP", quality=WEBP_QUALITY, optimize=True, method=6)
    except Exception as e: print(f"Gagal proses {src}: {e}")

def process_photos(kode, photo_paths):
    links, cleaned, seen = [], [], set()
    for p in photo_paths:
        if str(p) not in seen:
            seen.add(str(p)); cleaned.append(p)
    for i, src in enumerate(tqdm(cleaned[:MAX_PHOTOS], desc=f"Photos {kode}", leave=False), start=1):
        filename = f"{kode}_{i}.webp"
        resize_and_compress_webp(src, IMG_DIR / filename)
        links.append(f"{PHOTO_URL_PREFIX}{filename}")
    return links

def parse_telegram_text(raw_text):
    if isinstance(raw_text, str): return " ".join(raw_text.split())
    if isinstance(raw_text, list):
        parts = [item.get("text", "") if isinstance(item, dict) else item for item in raw_text]
        return " ".join("".join(parts).split())
    return ""

def extract_units(src_code, base_url):
    folder = EXPORT_ROOT / src_code
    path = folder / "result.json"
    if not path.exists(): return []
    with open(path, "r", encoding="utf-8") as f: data = json.load(f)
    msgs = sorted([m for m in data.get("messages", []) if m.get("type") == "message" and m.get("photo")], key=lambda x: x.get("id", 0))
    grouped, current_group, last_ts, group_index = {}, [], None, 0
    for m in msgs:
        ts = int(m.get("date_unixtime", 0))
        if last_ts is None or abs(ts - last_ts) <= TIME_WINDOW: current_group.append(m)
        else:
            grouped[f"time_album_{group_index}"] = current_group
            group_index += 1; current_group = [m]
        last_ts = ts
    if current_group: grouped[f"time_album_{group_index}"] = current_group
    units = []
    for group in grouped.values():
        text_candidates = [(m, parse_telegram_text(m.get("text", "")).strip()) for m in group if parse_telegram_text(m.get("text", ""))]
        if not text_candidates: continue
        cap_msg, caption = max(text_candidates, key=lambda x: len(x[1]))
        if len(caption) < 30: continue
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

def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    print("\nConnecting Google Sheet...")
    sheet = connect_sheet()
    headers = sheet.row_values(1)
    all_rows = sheet.get_all_values()[1:]
    
    link_idx = headers.index("LINK_MESSAGE")
    kode_idx = headers.index("KODE_UNIT")
    
    existing_links = {r[link_idx] for r in all_rows if len(r) > link_idx and r[link_idx]}
    nums = [int(r[kode_idx][3:]) for r in all_rows if len(r) > kode_idx and r[kode_idx].startswith("BBK")]
    next_idx = max(nums) + 1 if nums else 1

    print("Scanning Telegram exports...\n")
    all_units = [u for src, base_url in SOURCE_MAP.items() for u in extract_units(src, base_url) if u["link"] not in existing_links]
    print(f"Total unit baru: {len(all_units)}\n")

    rows_to_append = []
    for u in tqdm(all_units, desc="Processing Units"):
        kode = f"BBK{next_idx:04d}"
        next_idx += 1
        photo_data = process_photos(kode, u["photos"])
        
        row_dict = {
            "KODE_UNIT": kode,
            "SOURCE_GROUP": u["src"],
            "LINK_MESSAGE": u["link"],
            "CAPTION_RAW": u["caption"],
            "PHOTO_URLS": "|".join(photo_data),
            "FETCH_DATE": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "LAST_SEEN_DATE": u["tanggal"],
            "LOKASI_GUDANG": WAREHOUSE_MAP.get(u["src"], "Gudang Pusat"),
            "STATUS_UNIT": "Tersedia",
            "IS_PROCESSED": "FALSE"
        }
        
        row = [row_dict.get(h, "") for h in headers]
        rows_to_append.append(row)
        existing_links.add(u["link"])

    # --- BAGIAN UPLOAD: BATCHING PER 10 BARIS + RETRY MECHANISM ---
    if rows_to_append:
        chunk_size = 10
        total_rows = len(rows_to_append)
        max_attempts = 3
        
        print(f"\nMemulai pengunggahan data (Total: {total_rows} baris, dibagi per {chunk_size} baris)...")
        
        for i in range(0, total_rows, chunk_size):
            chunk = rows_to_append[i:i + chunk_size]
            success = False
            
            # Loop retry untuk setiap batch individu jika terjadi gangguan sinyal/timeout
            for attempt in range(max_attempts):
                try:
                    print(f"Mengunggah baris ke-{i+1} sampai {min(i+chunk_size, total_rows)} (Percobaan {attempt + 1})...")
                    sheet.append_rows(chunk, value_input_option="USER_ENTERED")
                    success = True
                    break  # Sukses, keluar dari loop retry untuk batch berjalan
                except (ReadTimeout, Exception) as e:
                    print(f"   [!] Gagal mengunggah batch ini karena: {e}")
                    if attempt < max_attempts - 1:
                        print("   Menunggu 5 detik sebelum mencoba lagi...")
                        time.sleep(5)
                    else:
                        print("\n[ERROR] Gagal mengunggah setelah 3 kali percobaan pada batch ini.")
                        raise e
            
            if success:
                # Beri jeda 1 detik antar batch untuk mencegah menyentuh limits kuota Google API
                time.sleep(1)
                
        print(f"\nBerhasil menulis total {total_rows} unit baru ke Google Sheets.")
    else:
        print("\nTidak ada data baru untuk diunggah.")
    
    print("\nSelesai semua.")

if __name__ == "__main__":
    main()