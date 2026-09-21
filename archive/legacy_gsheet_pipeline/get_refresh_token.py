# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Set console encoding to UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"

def main():
    if not CLIENT_SECRETS_FILE.exists():
        print("\n========================================================")
        print("[-] FILE 'client_secrets.json' TIDAK DITEMUKAN!")
        print("========================================================")
        print("Langkah untuk mendapatkan file ini:")
        print("1. Buka Google Cloud Console: https://console.cloud.google.com/")
        print("2. Pilih proyek GCP Anda.")
        print("3. Buka menu 'APIs & Services' -> 'Credentials'.")
        print("4. Klik 'Create Credentials' -> 'OAuth client ID'.")
        print("   *(Jika diminta configure OAuth Consent Screen, pilih 'External',")
        print("   lalu masukkan email Anda sebagai 'Test Users' agar bisa login).*")
        print("5. Pilih Application Type: 'Desktop app'.")
        print("6. Klik 'Create', lalu klik tombol download JSON.")
        print(f"7. Rename file tersebut menjadi 'client_secrets.json' dan simpan di folder:\n   {CLIENT_SECRETS_FILE}")
        print("========================================================\n")
        return

    # Scope untuk mengakses Google Drive
    scopes = ["https://www.googleapis.com/auth/drive"]

    try:
        print("[+] Memulai proses autentikasi...")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes)
        # Menjalankan server lokal untuk menerima callback login dari browser
        creds = flow.run_local_server(port=0)

        print("\n========================================================")
        print("🎉 AUTENTIKASI BERHASIL! 🎉")
        print("========================================================\n")
        print("Salin informasi di bawah ini untuk GitHub Secrets:\n")
        print(f"CLIENT_ID       : {creds.client_id}")
        print(f"CLIENT_SECRET   : {creds.client_secret}")
        print(f"REFRESH_TOKEN   : {creds.refresh_token}")
        print("\n========================================================")
        print("Simpan ketiga nilai tersebut. Kita akan memasukkannya")
        print("ke GitHub Secrets agar upload foto berjalan lancar.")
        print("========================================================\n")

    except Exception as e:
        print(f"[-] Terjadi kesalahan saat autentikasi: {e}")

if __name__ == "__main__":
    main()
