#!/usr/bin/env python3
"""
BBKitchen R2 Fast Photo Uploader.
Uploads 5,511 WebP master photos to Cloudflare R2 bucket with multi-threading & resume support.
"""

import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
from botocore.config import Config
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ================= KONFIGURASI SUMBER FOTO =================
POSSIBLE_PATHS = [
    Path(r"C:\Users\Lenovo\My Drive\BBK_WEBP_MASTER"),
    Path(r"G:\My Drive\BBK_WEBP_MASTER"),
]
SOURCE_DIR = next((p for p in POSSIBLE_PATHS if p.exists()), POSSIBLE_PATHS[0])
STATE_FILE = Path(__file__).parent / "r2_uploaded_cache.txt"
BUCKET_NAME = "bbk-assets"

def get_r2_client(account_id, access_key, secret_key):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", max_pool_connections=25)
    )

def load_cached_uploads():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def append_cached_upload(filename):
    with open(STATE_FILE, "a", encoding="utf-8") as f:
        f.write(f"{filename}\n")

def upload_single_photo(s3_client, file_path, bucket_name):
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

def main():
    print("=" * 60)
    print("🚀 BBKITCHEN CLOUDFLARE R2 BATCH PHOTO UPLOADER")
    print("=" * 60)

    # 1. Validasi Folder Sumber
    if not SOURCE_DIR.exists():
        print(f"[-] Error: Folder sumber tidak ditemukan di {SOURCE_DIR}")
        print("    Pastikan Google Drive Anda terpasang (G:\\My Drive\\BBK_WEBP_MASTER).")
        return

    # 2. Ambil Kredensial dari Environment atau Input
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

    if not (account_id and access_key and secret_key):
        print("\nSilakan masukkan kredensial Cloudflare R2 Anda:")
        account_id = input("1. Account ID         : ").strip()
        access_key = input("2. Access Key ID      : ").strip()
        secret_key = input("3. Secret Access Key  : ").strip()

    if not (account_id and access_key and secret_key):
        print("[-] Error: Kredensial R2 tidak lengkap!")
        return

    print("\n[+] Menghubungkan ke Cloudflare R2...")
    s3_client = get_r2_client(account_id, access_key, secret_key)

    # 3. Scanning file WebP
    print(f"[+] Memindai file WebP di {SOURCE_DIR}...")
    all_files = list(SOURCE_DIR.glob("*.webp"))
    total_found = len(all_files)
    print(f"[+] Ditemukan total: {total_found} file WebP.")

    # 4. Filter file yang sudah pernah di-upload (Resume support)
    uploaded_cache = load_cached_uploads()
    pending_files = [f for f in all_files if f.name not in uploaded_cache]
    print(f"[+] Sudah terunggah sebelumnya : {len(uploaded_cache)} file.")
    print(f"[+] File yang akan diunggah    : {len(pending_files)} file.\n")

    if not pending_files:
        print("🎉 Semua foto sudah terunggah 100% ke Cloudflare R2! Tidak ada tugas tersisa.")
        return

    # 5. Multi-Threaded Upload
    MAX_WORKERS = 10
    success_count = 0
    fail_count = 0

    print(f"[*] Memulai pengunggahan paralel ({MAX_WORKERS} worker threads)...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(upload_single_photo, s3_client, f, BUCKET_NAME): f for f in pending_files}
        
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

if __name__ == "__main__":
    main()
