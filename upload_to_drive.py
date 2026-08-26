# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Set console encoding to UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
# Folder output WebP master
WEBP_DIR = BASE_DIR.parent / "BBK_WEBP_MASTER"
SERVICE_ACCOUNT_FILE = BASE_DIR / "credentials.json"

def main():
    # Ambil folder ID Google Drive dari environment variable
    folder_id = os.getenv("GDRIVE_FOLDER_ID")
    if not folder_id:
        print("[-] Error: Env 'GDRIVE_FOLDER_ID' tidak ditemukan!")
        return

    if not SERVICE_ACCOUNT_FILE.exists():
        print(f"[-] Error: File credentials tidak ditemukan di {SERVICE_ACCOUNT_FILE}")
        return

    if not WEBP_DIR.exists():
        print(f"[-] Info: Folder {WEBP_DIR} tidak ditemukan atau kosong. Tidak ada foto untuk di-upload.")
        return

    # Ambil daftar file .webp
    webp_files = list(WEBP_DIR.glob("*.webp"))
    if not webp_files:
        print("[+] Info: Tidak ada file .webp baru untuk di-upload.")
        return

    print(f"[+] Menghubungkan ke Google Drive API...")
    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    service = build("drive", "v3", credentials=creds)

    print(f"[+] Mulai mengunggah {len(webp_files)} foto ke Google Drive (Folder ID: {folder_id})...")
    
    for file_path in webp_files:
        filename = file_path.name
        print(f"  -> Mengunggah {filename}...", end="", flush=True)
        
        try:
            # Metadata file di Google Drive
            file_metadata = {
                "name": filename,
                "parents": [folder_id]
            }
            
            media = MediaFileUpload(
                str(file_path),
                mimetype="image/webp",
                resumable=True
            )
            
            # Cek apakah file dengan nama yang sama sudah ada di folder tersebut
            # untuk menghindari duplikasi upload jika workflow di-run ulang
            query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
            results = service.files().list(q=query, fields="files(id)").execute()
            items = results.get("files", [])
            
            if items:
                print(" [Sudah Ada - Dilewati]")
                continue
                
            # Jalankan proses upload
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()
            
            print(f" [Sukses! ID: {file.get('id')}]")
            
        except Exception as e:
            print(f" [GAGAL: {e}]")

    print("[+] Proses upload foto selesai.")

if __name__ == "__main__":
    main()
