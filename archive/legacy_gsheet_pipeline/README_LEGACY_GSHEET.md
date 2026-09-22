# 📦 ARSIP LENGKAP: BBKitchen Legacy Google Sheets & Google Drive Pipeline

> **Status:** Kapsul Arsip Cadangan Resmi (100% Utuh & Self-Contained)  
> **Tujuan:** Garansi pemulihan jika sewaktu-waktu dibutuhkan untuk menjalankan sistem versi Google Sheets lama.

---

## 🏛️ 1. Peta Alur Kerja Legacy (Masa Lalu):
Sistem lama berjalan dengan rantai berikut:
1. **GitHub Actions (`run-bbk.yml.bak`):** Berjalan terjadwal di Cloud (cron setiap 3 jam).
2. **Runner (`run_cloud.py` / `run.py`):** Mengorkestrasi pemanggilan skrip fetch & parse.
3. **Telethon Fetch & Parser (`telegram_parser_to_gsheet.py`):**
   - Mengambil pesan Telegram dari 12 grup mitra.
   - Mengelompokkan pesan ke format album 15 detik.
   - Menempel watermark `logo.png` dan mengompres ke WebP (`BBK_WEBP_MASTER/`).
   - Menulis data baris produk mentah ke Google Sheets spreadsheet `BBK_MASTER_SYSTEM` (tab `RAW_INVENTORY`).
4. **Drive Uploader (`upload_to_drive.py`):**
   - Mengunggah foto WebP dari folder master lokal ke Google Drive menggunakan OAuth Refresh Token.
5. **Pembersih File (`clean_files.py`):**
   - Menghapus media temporer yang sudah selesai diproses.

---

## 📁 2. Daftar File Kapsul Arsip:
- `run.py`: Script runner lokal versi Google Sheets.
- `run_cloud.py`: Script runner cloud untuk GitHub Actions.
- `telegram_parser_to_gsheet.py`: Mesin parser Telethon + Watermark + GSheet Writer.
- `upload_to_drive.py`: Mesin uploader foto WebP ke Google Drive.
- `clean_files.py`: Pembersih folder temp lokal.
- `run-bbk.yml.bak`: Cetak biru workflow GitHub Actions lama.
- `client_secrets.json` & `get_refresh_token.py`: Konfigurasi OAuth Google.
- `BBK_MASTER_SYSTEM.xlsx`: Backup file master Excel lokal.

---

## ⚙️ 3. Cara Menjalankan Versi Legacy (Jika Dibutuhkan):
```bash
# Di dalam folder ini:
python run.py --start 2026-08-01 --end 2026-08-25
```
