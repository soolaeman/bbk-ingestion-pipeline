#!/usr/bin/env python3
"""
BBKitchen Autonomous Ingestion Engine.
Direct Telegram/Raw intake -> Deterministic Regex Parsing -> WebP Optimization
-> Cloudflare R2 Upload -> SQLite SSOT & Turso Edge DB Sync.
Replaces legacy Google Appscript and eliminates OpenAI API costs ($0 Opex).
"""

import os
import re
import sys
import json
import sqlite3
import argparse
import urllib.request
from datetime import datetime
from pathlib import Path
from PIL import Image
import boto3
from botocore.config import Config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Cloudflare R2 Configuration
R2_BUCKET = "bbk-assets"
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "60e1d09df95bb97b2f4f107386d302a9")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID", "51bf8015c9ff8ec55fc92df27f87fa3f")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "b3bf8ee5b565a0c3f5ea7c166d333469df8fa68c783c27da2e2e71d34c0e6205")
R2_PUBLIC_BASE = "https://pub-946d1fe1a1b1461eb2cca6be4462ba11.r2.dev"

# Turso Cloud Database Configuration
TURSO_URL = "https://bbk-soolaeman.aws-ap-northeast-1.turso.io/v2/pipeline"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODk4MjI2ODcsImlkIjoiMDFhMGI5YmQtZTIwMS03ZjUxLWExMDQtMzk5NzlkNjAzMTNiIiwia2lkIjoickFjZFotQXpjdjkwZE5pLWd6aHF4ZWZPN1dzNTJnMjB3VmNtQld1bS1UcyIsInJpZCI6IjgwYzI0OTQ1LTRmMDctNGYwNy05YzJkLTdhYmFlZGFjMzNlYSJ9.qavUPG-VqnaFxPUHsi7OV_7uesPTMk2K3Tn35YueMnq4hR0KJDhZ-rc4zzCpatWWovjCCJQ0LTpINp_KRC2vCA"

def get_db_connection():
    possible_paths = [
        Path(__file__).parent.parent / "Jarvis-OS" / "domains" / "business" / "bbkitchen" / "data" / "bbk.db",
        Path(__file__).parent / "bbk.db",
        Path(r"c:\Users\Lenovo\Documents\Github\JARVIS\Jarvis-OS\domains\business\bbkitchen\data\bbk.db"),
    ]
    for p in possible_paths:
        if p.exists():
            return sqlite3.connect(str(p))
    raise FileNotFoundError("Database bbk.db tidak ditemukan!")

def get_next_sku(conn):
    c = conn.cursor()
    c.execute("SELECT MAX(CAST(SUBSTR(sku, 4) AS INTEGER)) FROM products WHERE sku LIKE 'BBK%'")
    row = c.fetchone()
    max_num = row[0] if row and row[0] is not None else 3097
    next_num = max_num + 1
    return f"BBK{str(next_num).zfill(4)}"

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")

def parse_price(text):
    m = re.search(r"harga\s*[:=\s]*([0-9.,]+)\s*(jt|juta)?", text, re.IGNORECASE)
    if not m:
        m = re.search(r"([0-9.,]+)\s*(jt|juta)", text, re.IGNORECASE)
    if not m:
        return None
    val_str = m.group(1).replace(".", "").replace(",", ".")
    unit = m.group(2)
    try:
        val = float(val_str)
        if unit and unit.lower() in ("jt", "juta"):
            val = val * 1000000
        elif val < 10000:
            val = val * 1000000
        return val
    except:
        return None

def match_category(caption):
    lower = caption.lower()
    if "sink" in lower or "bak cuci" in lower:
        if "2" in lower or "double" in lower: return "double-sink-stainless"
        if "3" in lower or "triple" in lower: return "triple-sink-stainless"
        if "jumbo" in lower: return "sink-jumbo-stainless"
        return "single-sink-stainless"
    if "meja" in lower or "table" in lower:
        if "1 susun" in lower: return "meja-1-susun-stainless"
        if "2 susun" in lower: return "meja-2-susun-stainless"
        if "3 susun" in lower: return "meja-3-susun-stainless"
        if "kabinet" in lower or "cabinet" in lower: return "meja-kabinet-stainless"
        if "kompor" in lower: return "meja-kompor-stainless"
        if "bumbu" in lower: return "meja-bumbu-stainless"
        return "meja-2-susun-stainless"
    if "kompor" in lower or "burner" in lower or "tungku" in lower or "kwali" in lower or "stove" in lower:
        if "1 tungku" in lower: return "kompor-1-tungku"
        if "2 tungku" in lower: return "kompor-2-tungku"
        if "3 tungku" in lower: return "kompor-3-tungku"
        if "4 tungku" in lower or "4 burner" in lower: return "kompor-4-tungku"
        if "6 tungku" in lower or "6 burner" in lower: return "kompor-6-tungku"
        if "kwali" in lower or "wok" in lower: return "kompor-wok-kwali-range"
        if "grill" in lower: return "kompor-grill-tepanyaki"
        return "kompor-4-tungku"
    if "chiller" in lower:
        if "undercounter" in lower: return "undercounter-chiller"
        if "upright" in lower: return "upright-chiller"
        return "undercounter-chiller"
    if "freezer" in lower or "frezzer" in lower:
        if "chest" in lower: return "chest-freezer"
        if "upright" in lower: return "upright-freezer"
        return "chest-freezer"
    if "hood" in lower or "exhaust" in lower: return "hood"
    if "ice" in lower or "es" in lower: return "ice-bin"
    if "rak" in lower: return "rak-4-susun-stainless"
    if "showcase" in lower: return "showcase-1-pintu"
    if "fryer" in lower: return "deep-fryer"
    if "oven" in lower: return "oven"
    return "peralatan-dapur-bekas-lainnya"

def extract_title(caption):
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    first_line = lines[0] if lines else "Peralatan Dapur Komersial"
    clean = re.sub(r"[*_#]", "", first_line).strip()
    clean = re.sub(r"^\d+[\.\)]\s*", "", clean)
    if len(clean) > 80:
        clean = clean[:80].rsplit(" ", 1)[0]
    return clean.capitalize()

def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4")
    )

def optimize_and_upload_photo(s3_client, file_path, sku, index):
    try:
        im = Image.open(file_path)
        im = im.convert("RGB")
        max_size = 1600
        if max(im.size) > max_size:
            im.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        target_filename = f"{sku}_{index}.webp"
        temp_path = Path(file_path).parent / f"temp_{target_filename}"
        im.save(temp_path, "WEBP", quality=85)

        s3_client.upload_file(
            Filename=str(temp_path),
            Bucket=R2_BUCKET,
            Key=target_filename,
            ExtraArgs={"ContentType": "image/webp", "CacheControl": "public, max-age=31536000, immutable"}
        )
        if temp_path.exists():
            temp_path.unlink()
        return True, target_filename
    except Exception as e:
        return False, str(e)

def execute_turso_single(sql, params):
    turso_args = []
    for p in params:
        if p is None:
            turso_args.append({"type": "null"})
        elif isinstance(p, (int, bool)):
            turso_args.append({"type": "integer", "value": str(int(p))})
        elif isinstance(p, float):
            turso_args.append({"type": "float", "value": float(p)})
        else:
            turso_args.append({"type": "text", "value": str(p)})

    payload = {"requests": [{"type": "execute", "stmt": {"sql": sql, "args": turso_args}}]}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        TURSO_URL,
        data=data,
        headers={"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        for r in res.get("results", []):
            if r.get("type") == "error":
                raise Exception(r.get("error", {}).get("message", "Unknown Turso Error"))
        return res

def process_intake(caption, photo_paths=None, location_override=None, dry_run=False):
    conn = get_db_connection()
    sku = get_next_sku(conn)

    # 1. Parse fields
    title = extract_title(caption)
    cat_slug = match_category(caption)
    raw_price = parse_price(caption) or 2500000.0

    kondisi = "BEKAS"
    if "BARU" in caption.upper(): kondisi = "BARU"

    lokasi = location_override or "PAMULANG 2"
    if not location_override:
        if "SAWANGAN" in caption.upper(): lokasi = "SAWANGAN"
        elif "SETU" in caption.upper(): lokasi = "SETU"
        elif "KEDAUNG" in caption.upper(): lokasi = "KEDAUNG"
        elif "BARAT" in caption.upper(): lokasi = "PAMULANG BARAT"

    # Pricing calculations
    harga_modal = round(raw_price * 0.70, -3)
    harga_buka = float(raw_price)
    harga_deal = round(raw_price * 0.92, -3)
    harga_floor = round(raw_price * 0.82, -3)
    margin_deal = harga_deal - harga_modal
    margin_floor = harga_floor - harga_modal

    slug = f"{slugify(title)}-{sku.lower()}"
    link_unit = f"https://www.bukanbarukitchen.com/shop/{slug}/"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    short_desc = f"{title} siap pakai, jaminan fungsi normal ex-resto komersial. Hubungi BBKitchen untuk survei fisik & nego."
    full_desc = f"<p>{title} kondisi {kondisi.lower()} siap pakai di gudang {lokasi}.</p><p>{caption.replace('\n', '<br>')}</p>"

    # Format photo URLs
    photo_urls_list = []
    if photo_paths:
        for idx in range(1, len(photo_paths) + 1):
            photo_urls_list.append(f"{R2_PUBLIC_BASE}/{sku}_{idx}.webp")
    else:
        photo_urls_list.append(f"{R2_PUBLIC_BASE}/{sku}_1.webp")

    photo_urls_str = ",".join(photo_urls_list)

    print("\n" + "=" * 65)
    print(f"📦 BBKITCHEN UNIT INTAKE PREVIEW — {sku}")
    print("=" * 65)
    print(f"• SKU              : {sku}")
    print(f"• Judul Produk     : {title}")
    print(f"• Kategori         : {cat_slug}")
    print(f"• Lokasi Gudang    : {lokasi}")
    print(f"• Kondisi          : {kondisi}")
    print(f"• Harga Modal      : Rp {harga_modal:,.0f}")
    print(f"• Harga Buka (WA)  : Rp {harga_buka:,.0f}")
    print(f"• Harga Deal Target: Rp {harga_deal:,.0f} (Margin: Rp {margin_deal:,.0f})")
    print(f"• Harga Floor Mini : Rp {harga_floor:,.0f} (Margin: Rp {margin_floor:,.0f})")
    print(f"• Storefront URL   : {link_unit}")
    print("=" * 65)

    if dry_run:
        print("[*] Mode DRY-RUN: Data tidak disimpan ke database atau R2.")
        return

    # 2. Upload photos to R2
    if photo_paths:
        s3 = get_r2_client()
        print(f"\n[+] Mengunggah {len(photo_paths)} foto ke Cloudflare R2 ({R2_BUCKET})...")
        for idx, p in enumerate(photo_paths, start=1):
            ok, msg = optimize_and_upload_photo(s3, p, sku, idx)
            if ok:
                print(f"    -> Foto {idx} ({msg}) terunggah sukses.")
            else:
                print(f"    [!] Gagal foto {idx}: {msg}")

    # 3. Insert to SQLite
    record = (
        sku, title, f"{title} | BBKitchen", cat_slug, "READY", "PUBLISHED",
        lokasi, kondisi, short_desc, full_desc, f"{title.lower()} bekas",
        short_desc[:160], None, photo_urls_str, now_str, None, None,
        "", sku, 0, f"{title} - BBKitchen", f"{title} Siap Pakai",
        f"Fisik unit {title} di {lokasi}", f"Dokumentasi stok {title} di BBKitchen",
        "PY", harga_modal, harga_buka, harga_deal, harga_floor,
        margin_floor, margin_deal, "SAFE", None, link_unit
    )

    c = conn.cursor()
    insert_sql = """
        INSERT OR REPLACE INTO products (
            sku, title, seo_title, category_slug, status_unit, status_pipeline,
            lokasi_unit, kondisi_unit, short_description, full_description,
            yoast_keyword, yoast_description, featured_image, photo_urls,
            tanggal_masuk, tanggal_terjual, durasi_terjual, link_telegram,
            product_id_woo, is_dirty, image_alt, image_title, image_caption,
            image_description, asal_gudang, harga_modal, harga_buka_wa,
            harga_deal_wa, harga_floor_wa, margin_floor, margin_deal,
            status_guardrail, last_checked_telegram, link_unit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    c.execute(insert_sql, record)
    conn.commit()
    print("\n[+] Berhasil disimpan ke SQLite SSOT (bbk.db)!")

    # 4. Sync to Turso
    print("[+] Sinkronisasi langsung ke Turso Cloud Database...")
    execute_turso_single(insert_sql, record)
    print("    -> Ter-deploy live di Turso Cloud Edge Database!")
    print(f"\n🎉 SUKSES! Unit {sku} sekarang LIVE dan siap dipasarkan!")

def main():
    parser = argparse.ArgumentParser(description="BBKitchen Autonomous Intake Engine")
    parser.add_argument("-c", "--caption", help="Teks caption postingan Telegram")
    parser.add_argument("-p", "--photos", help="Daftar file foto dipisah koma (e.g. img1.jpg,img2.jpg)")
    parser.add_argument("-l", "--location", help="Override lokasi unit (e.g. SAWANGAN)")
    parser.add_argument("--dry-run", action="store_true", help="Uji coba parse tanpa menyimpan ke database")

    args = parser.parse_args()

    caption = args.caption
    if not caption:
        print("=" * 60)
        print("📥 BBKITCHEN AUTONOMOUS INTAKE CLI")
        print("=" * 60)
        print("Silakan tempel caption Telegram (tekan Enter dua kali atau Ctrl+Z lalu Enter jika selesai):")
        lines = []
        try:
            while True:
                line = input()
                if not line and lines and not lines[-1]:
                    break
                lines.append(line)
        except EOFError:
            pass
        caption = "\n".join(lines).strip()

    if not caption:
        print("[-] Error: Caption tidak boleh kosong!")
        return

    photo_paths = []
    if args.photos:
        photo_paths = [Path(p.strip()) for p in args.photos.split(",") if p.strip()]

    process_intake(caption, photo_paths, args.location, args.dry_run)

if __name__ == "__main__":
    main()
