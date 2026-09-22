import sys
import os
import shutil
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ================= KONFIGURASI =================
BASE_DIR = Path(r"G:\My Drive\Automation")
IMG_SOURCE_DIR = Path(r"G:\My Drive\BBK_WEBP_MASTER")
ARCHIVE_DIR = BASE_DIR / "archive"
SERVICE_ACCOUNT_FILE = BASE_DIR / "credentials.json"
SPREADSHEET_NAME = "BBK_MASTER_SYSTEM"
WORKSHEET_NAME = "MASTER_INVENTORY"

def clean_published():
    # Pastikan folder arsip ada
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Autentikasi API
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    
    print("Menghubungkan ke Google Sheets...")
    sheet = client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)
    
    # 2. Ambil semua data
    rows = sheet.get_all_values()
    headers = rows[0]
    data = rows[1:]
    
    # Debug: Pastikan header terbaca dengan benar
    try:
        idx_kode = headers.index("SKU")
        idx_status = headers.index("STATUS_PIPELINE")
    except ValueError as e:
        print(f"Error: Kolom tidak ditemukan di Sheet! Pastikan header adalah 'SKU' dan 'STATUS_PIPELINE'.")
        print(f"Header yang terbaca: {headers}")
        return
    
    updates = []
    print(f"Memeriksa {len(data)} produk...")
    
    # 3. Looping data
    for i, row in enumerate(data):
        kode = row[idx_kode]
        status = row[idx_status]
        
        if status == "PUBLISHED" and kode:
            # Cari file yang namanya diawali kode SKU (misal: BBK0051_*)
            files_found = list(IMG_SOURCE_DIR.glob(f"{kode}_*"))
            
            if files_found:
                for file_path in files_found:
                    try:
                        dest_path = ARCHIVE_DIR / file_path.name
                        shutil.move(str(file_path), str(dest_path))
                        print(f"✅ Diarsipkan: {file_path.name}")
                    except Exception as e:
                        print(f"❌ Gagal memindahkan {file_path.name}: {e}")
                
                # Tandai baris di Google Sheets untuk dikosongkan (Kolom M dan N)
                row_num = i + 2
                updates.append({'range': f"M{row_num}:N{row_num}", 'values': [["", ""]]})
    
    # 4. Batch Update ke Sheets
    if updates:
        sheet.batch_update(updates)
        print(f"\n✨ Selesai! {len(updates)} produk dibersihkan dari Sheet.")
    else:
        print("\nTidak ada data PUBLISHED baru yang perlu dibersihkan.")

if __name__ == "__main__":
    clean_published()