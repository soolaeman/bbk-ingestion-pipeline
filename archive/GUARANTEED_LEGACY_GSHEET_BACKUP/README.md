# 🔒 GUARANTEED LEGACY GSHEET & GDRIVE PIPELINE BACKUP
> **Location:** `bbk-ingestion-pipeline/archive/GUARANTEED_LEGACY_GSHEET_BACKUP/`  
> **Status:** Sealed Snapshot (Pencadangan Mutlak Versi Google Sheet & Google Drive)

Folder ini memuat salinan lengkap dan murni dari seluruh skrip otomasi pipeline **Google Sheets + Google Drive + WooCommerce** era sebelum migrasi ke Turso Cloud Edge & Next.js:

---

### 📂 Daftar File & Fungsinya:

1. **`telegram_parser_to_gsheet.py`**:
   - Parser utama Telegram, pengelompokan album (time window 15s), watermarking logo, konversi WebP, dan penulisan baris baru ke spreadsheet `BBK_MASTER_SYSTEM` (worksheet `RAW_INVENTORY`).
2. **`upload_to_drive.py`**:
   - Skrip pengunggah foto WebP master dari lokal ke Google Drive folder ID via Google Drive API (OAuth refresh token).
3. **`autonomous_telegram_sync.py`**:
   - Versi transisi sinkronisasi otonom Telegram langsung.
4. **`run_cloud.py` & `run.py`**:
   - Entrypoint eksekusi harian era Google Sheets.
5. **`run-bbk.yml.bak`**:
   - File konfigurasi workflow GitHub Actions asli (cron setiap 3 jam).
6. **`BBK_MASTER_SYSTEM.xlsx`**:
   - File spreadsheet master sistem offline.
7. **`CMD_GOOGLE.bat`, `run.bat`, `run_scheduled.bat`, `clean_files.bat`**:
   - Batch file eksekusi shortcut Windows.
8. **`get_refresh_token.py` & `client_secrets.json`**:
   - Skrip otentikasi Google API OAuth.

---
*Snapshot ini dilindungi dan tidak akan diubah atau dihapus oleh proses modernisasi apa pun.*
