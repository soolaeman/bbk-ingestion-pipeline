# ⚙️ BBKitchen Sovereign Ingestion Pipeline Engine

> **Pusat otomatisasi penarikan pesan Telegram mitra, kurasi AI, watermarking WebP, dan sinkronisasi katalog cloud edge BBKitchen.**

---

## 🏛️ Arsitektur Pipeline (2-Stage Staging)

```
[ Telegram Mitra ]
       │
       ▼ (1. Fetch)
[ SQLite: tabel `raw_pipeline` ]  <-- STAGING MENTAH (Zero Data Loss)
       │
       ▼ (2. Normalize + Watermark)
[ AI Gateway + SSOT Engine ]     <-- 58 Kategori WooCommerce & 6 Hub Fisik
       │
       ▼
[ SQLite: tabel `products` ]      <-- KATALOG BERSIH (bbk.db)
       │
       ▼ (3. Sync)
[ Git SSOT Replication ]          <-- DISTRIBUSI LOKAL & CLOUD
       │
       ├──► [ Storefront Web (bukanbarukitchen.com) ]
       └──► [ Control Tower ERP (Internal Bisnis) ]
```

---

## 🎮 Single Entry Point: `bbk_pipeline.py`

Hanya ada **1 file remote control** di root direktori yang Anda jalankan:

```powershell
# 1. Tarik pesan & foto mentah dari seluruh grup mitra Telegram
python bbk_pipeline.py fetch [--limit 50]

# 2. Kurasi AI & petakan ke 58 kategori SSOT & 6 hub fisik
python bbk_pipeline.py normalize [--limit 10] [--dry-run]

# 3. Replikasi database master SQLite ke repo storefront & control tower
python bbk_pipeline.py sync

# 4. EKSEKUSI LENGKAP END-TO-END (Dipakai untuk jadwal otomatis harian / cloud)
python bbk_pipeline.py run-all
```

---

## 🧠 Direktori Mesin Internal: `core/`

Seluruh kerumitan kode internal disimpan rapi di dalam folder [`core/`](core/), berikut fungsi masing-masing modul:

### 1. `core/telethon_fetch.py` *(Tangan Penarik Telegram)*
* **Fungsi:** Menghubungkan script ke akun Telegram via Telethon MTProto API.
* **Tugas:** Menscan channel-channel mitra (GK, BB, ML, PE, WT, PY, SK, RK, dll.), mengunduh teks caption mentah, dan menyedot foto asli ke folder lokal.

### 2. `core/watermark_engine.py` *(Pabrik Watermark & WebP)*
* **Fungsi:** Pengolahan citra dan aset visual otomatis.
* **Tugas:** 
  - Me-resize gambar ke resolusi standar komersial (max 1600px, filter LANCZOS).
  - Menempelkan watermark transparan [`logo.png`](core/logo.png) di posisi tengah atas (opacity 200).
  - Mengompres dan mengubah format ke **WebP kualitas 80** dengan penamaan standar SKU: `{SKU}_1.webp`, `{SKU}_2.webp`, dst.

### 3. `core/process_raw_pipeline.py` *(Otak Normalisasi AI & SSOT)*
* **Fungsi:** Mesin pembersih data katalog.
* **Tugas:** 
  - Membaca baris `PENDING` dari tabel `raw_pipeline`.
  - Mengirim prompt ke AI Gateway untuk mengekstrak nama alat, merk, dimensi, dan taksiran harga baru.
  - Memvalidasi slug ke **58 Kategori Resmi WooCommerce** ([`categories_ssot.json`](../Jarvis-OS/domains/business/bbkitchen/config/categories_ssot.json)).
  - Memetakan channel Telegram asli ke **6 Hub Fisik Jabodetabek** ([`warehouses_ssot.json`](../Jarvis-OS/domains/business/bbkitchen/config/warehouses_ssot.json)) tanpa halusinasi gudang fiktif.
  - Menyimpan hasil kurasi ke tabel `products`.

### 4. `core/ai_gateway.py` *(Gateway Multi-LLM Failover)*
* **Fungsi:** Penyedia kecerdasan buatan tanpa jeda.
* **Tugas:** Menghubungi Google AI Studio (**Gemini 3.6 Flash**) sebagai model utama, dan otomatis failover ke Groq Cloud (**Qwen / Llama**) jika terjadi limit atau gangguan jaringan, dengan jaminan output JSON terstruktur.

### 5. `core/sync_repos.py` *(Replikasi SQLite SSOT)*
* **Fungsi:** Replikasi master `bbk.db` ke repositori `bbk-storefront`, `bbk-control-tower`, dan `Jarvis-OS`.
* **Tugas:** Menjamin seluruh aplikasi holding membaca SQLite SSOT yang identik secara embedded tanpa network latency.

### 6. `core/sync_photos_to_r2.py` *(Pengunggah Aset Cloud)*
* **Fungsi:** Pengunggah foto multi-threading.
* **Tugas:** Mengunggah file foto WebP dari folder master lokal/Google Drive ke bucket **Cloudflare R2** (`bbk-assets`) agar bisa dibuka oleh pengunjung website lewat CDN global dengan latensi <100ms dan zero egress fee.

### 7. `core/config_telethon.py` *(Kredensial Telegram)*
* **Fungsi:** Menyimpan konfigurasi `API_ID`, `API_HASH`, dan session string Telethon.

---

## 📁 Struktur Direktori Bersih

```text
bbk-ingestion-pipeline/
├── 📁 core/                   <-- Modul-modul mesin internal di atas
├── 📁 archive/                <-- Arsip script & file era Google Sheet/Appscript lama
├── 📁 docs/                   <-- Dokumentasi teknis & progress
├── 🐍 bbk_pipeline.py         <-- Remote control utama CLI
├── .env                       <-- API Keys (Gemini, Groq, Cloudflare)
├── README.md                  <-- Dokumentasi ini
└── requirements.txt           <-- Dependensi Python (Telethon, Pillow, Requests, dll)
```
