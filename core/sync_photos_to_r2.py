#!/usr/bin/env python3
"""
BBKitchen R2 Fast Photo Uploader.
Uploads 5,511 WebP master photos to Cloudflare R2 bucket with multi-threading & resume support.
"""

import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import boto3
from botocore.config import Config
from tqdm import tqdm

# Load .env
env_paths = [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ================= KONFIGURASI SUMBER FOTO =================
EPHEMERAL_TEMP_DIR = Path(__file__).resolve().parent.parent / ".temp_webp"
EXPORTS_DIR = Path(__file__).resolve().parent / "exports"

SOURCE_DIR = EPHEMERAL_TEMP_DIR
STATE_FILE = Path(__file__).parent / "r2_uploaded_cache.txt"
LEGACY_STATE_FILE = Path(__file__).parent.parent / "archive" / "legacy_gsheet_pipeline" / "r2_uploaded_cache.txt"
BUCKET_NAME = os.getenv("R2_BUCKET", "bbk-assets")

# Default R2 credentials fallback
DEFAULT_ACCOUNT_ID = "60e1d09df95bb97b2f4f107386d302a9"
DEFAULT_ACCESS_KEY = "51bf8015c9ff8ec55fc92df27f87fa3f"
DEFAULT_SECRET_KEY = "b3bf8ee5b565a0c3f5ea7c166d333469df8fa68c783c27da2e2e71d34c0e6205"

def get_r2_client(account_id, access_key, secret_key):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=3,
            read_timeout=5,
            max_pool_connections=25
        )
    )

def load_cached_uploads():
    if not STATE_FILE.exists() and LEGACY_STATE_FILE.exists():
        try:
            import shutil
            shutil.copy(LEGACY_STATE_FILE, STATE_FILE)
        except Exception:
            pass

    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    elif LEGACY_STATE_FILE.exists():
        with open(LEGACY_STATE_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def append_cached_upload(filename):
    with open(STATE_FILE, "a", encoding="utf-8") as f:
        f.write(f"{filename}\n")

def upload_single_photo_rest(file_path, account_id, bucket_name, api_token):
    filename = file_path.name
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/r2/buckets/{bucket_name}/objects/{filename}"
    try:
        data = file_path.read_bytes()
        import urllib.request
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Authorization", f"Bearer {api_token}")
        req.add_header("Content-Type", "image/webp")
        with urllib.request.urlopen(req, timeout=15) as res:
            if res.status in (200, 201):
                append_cached_upload(filename)
                return True, filename
            else:
                return False, f"{filename}: HTTP {res.status}"
    except Exception as e:
        return False, f"{filename}: {e}"

def upload_single_photo_s3(s3_client, file_path, bucket_name):
    filename = file_path.name
    try:
        s3_client.upload_file(
            Filename=str(file_path),
            Bucket=bucket_name,
            Key=filename,
            ExtraArgs={"ContentType": "image/webp", "CacheControl": "public, max-age=31536000, immutable"}
        )
        append_cached_upload(filename)
        return True, filename
    except Exception as e:
        return False, f"{filename}: {e}"

def purge_ephemeral_buffers():
    """Membersihkan buffer foto raw Telegram dan temp WebP setelah sukses upload ke R2."""
    print("\n🧹 Membersihkan folder buffer temporary (Auto-Purge)...")
    
    # 1. Bersihkan .temp_webp
    if EPHEMERAL_TEMP_DIR.exists():
        for f in EPHEMERAL_TEMP_DIR.glob("*.webp"):
            try:
                f.unlink()
            except Exception:
                pass
        print(f"  [✓] Buffer ephemeral {EPHEMERAL_TEMP_DIR.name}/ disapu bersih.")

    # 2. Bersihkan file raw JPG di exports subfolders
    if EXPORTS_DIR.exists():
        for sub in EXPORTS_DIR.iterdir():
            if sub.is_dir():
                for jpg in sub.glob("*.jpg"):
                    try:
                        jpg.unlink()
                    except Exception:
                        pass
        print(f"  [✓] File raw JPG di {EXPORTS_DIR.name}/ disapu bersih.")

def main(auto_purge=True):
    print("=" * 60)
    print("🚀 BBKITCHEN CLOUDFLARE R2 BATCH PHOTO UPLOADER")
    print("=" * 60)

    # 1. Scanning buffer ephemeral .temp_webp
    all_files = list(SOURCE_DIR.glob("*.webp")) if SOURCE_DIR.exists() else []
    total_found = len(all_files)
    print(f"[+] Ditemukan total: {total_found} file WebP baru di buffer ephemeral (.temp_webp).")

    # 2. Ambil Kredensial
    account_id = os.getenv("R2_ACCOUNT_ID") or "8a991da706fc5fd18c527a4b67b8c5aa"
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    access_key = os.getenv("R2_ACCESS_KEY_ID") or DEFAULT_ACCESS_KEY
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY") or DEFAULT_SECRET_KEY
    bucket_name = os.getenv("R2_BUCKET", BUCKET_NAME)

    uploaded_cache = load_cached_uploads()
    pending_files = [f for f in all_files if f.name not in uploaded_cache]
    print(f"[+] Sudah terunggah sebelumnya : {len(uploaded_cache)} file.")
    print(f"[+] File yang akan diunggah    : {len(pending_files)} file.\n")

    if not pending_files:
        print("🎉 Semua foto sudah terunggah 100% ke Cloudflare R2! Tidak ada tugas tersisa.")
        if auto_purge:
            purge_ephemeral_buffers()
        return

    # 3. Tentukan Mode Upload: REST API (Bebas Sensor ISP) vs S3 Protocol
    use_rest_api = bool(api_token)
    s3_client = None

    if use_rest_api:
        print(f"🌐 Menggunakan Mode: Cloudflare REST API (https://api.cloudflare.com - Bebas Sensor ISP)")
    else:
        print(f"☁️ Menggunakan Mode: AWS S3 Protocol (https://{account_id}.r2.cloudflarestorage.com)")
        s3_client = get_r2_client(account_id, access_key, secret_key)
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except Exception as e:
            err_str = str(e)
            if "SSL" in err_str or "handshake" in err_str.lower() or "validation failed" in err_str.lower():
                print(f"\n⚠️ [ISP NOTICE] Koneksi ke Cloudflare S3 dicegat oleh ISP lokal.")
                print(f"   • Solusi: Set CLOUDFLARE_API_TOKEN di .env atau serahkan ke Cloud CI/CD.\n")
                return

    # 4. Multi-Threaded Upload
    MAX_WORKERS = 10
    success_count = 0
    fail_count = 0

    print(f"[*] Memulai pengunggahan paralel ({MAX_WORKERS} worker threads)...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        if use_rest_api:
            futures = {executor.submit(upload_single_photo_rest, f, account_id, bucket_name, api_token): f for f in pending_files}
        else:
            futures = {executor.submit(upload_single_photo_s3, s3_client, f, bucket_name): f for f in pending_files}

        with tqdm(total=len(pending_files), desc="Mengunggah ke R2", unit="foto") as pbar:
            for future in as_completed(futures):
                ok, msg = future.result()
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    tqdm.write(f"   [!] Gagal: {msg}")
                pbar.update(1)

    print("\n" + "=" * 60)
    print(f"🟢 PROSES SELESAI!")
    print(f"   • Sukses diunggah : {success_count} foto")
    print(f"   • Gagal           : {fail_count} foto")
    print(f"   • Total di R2     : {len(load_cached_uploads())} / {total_found} foto")
    print("=" * 60)

    # 5. Purge temporary buffers if successful
    if auto_purge and fail_count == 0:
        purge_ephemeral_buffers()

if __name__ == "__main__":
    main()
