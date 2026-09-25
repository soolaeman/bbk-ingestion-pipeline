# -*- coding: utf-8 -*-
"""
👑 BBKitchen Comprehensive Audit & Review Workbench Generator
Generates an interactive, human-fillable markdown workbook (AUDIT_REVIEW_WORKBENCH.md)
featuring direct Telegram message links, raw captions, parsed outputs, and quick-action checklists.
"""

import os
import sys
import json
import sqlite3
import time
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "..", "core")
for p in [BASE_DIR, CORE_DIR]:
    if p not in sys.path:
        sys.path.append(p)

from job_audit_regex_mvp import parse_regex_mvp, format_rupiah

DB_PATH = os.path.join(BASE_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db")
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, "..", "bbk.db")

WORKBENCH_PATH = os.path.join(BASE_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "docs", "notes", "AUDIT_REVIEW_WORKBENCH.md")

def generate_workbench():
    print(f"=== Generating BBKitchen Comprehensive Audit Review Workbench ===")
    print(f"Reading DB: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    prod_rows = cur.execute("SELECT sku, slug FROM products").fetchall()
    slug_map = {r["sku"]: r["slug"] for r in prod_rows if r["slug"]}

    raw_rows = cur.execute("SELECT kode_unit, source_group, caption_raw, link_message FROM raw_pipeline ORDER BY CAST(SUBSTR(kode_unit, 4) AS INTEGER) ASC").fetchall()
    total = len(raw_rows)

    klaster_non_product = []
    klaster_low_confidence = []
    klaster_missing_dim = []
    klaster_kondisi_baru = []
    klaster_peralatan_lainnya = []
    klaster_core_samples = []

    for r in raw_rows:
        sku = r["kode_unit"]
        caption = r["caption_raw"] or ""
        source_grp = r["source_group"] or ""
        link_msg = r["link_message"] or ""
        existing_slug = slug_map.get(sku)

        parsed = parse_regex_mvp(caption, sku, existing_slug=existing_slug, source_group=source_grp, link_msg=link_msg)
        parsed["link_message"] = link_msg

        if parsed["is_non_product"]:
            klaster_non_product.append(parsed)
        elif parsed["confidence"] == "LOW":
            klaster_low_confidence.append(parsed)
        elif parsed["category_slug"] == "peralatan-dapur-bekas-lainnya":
            klaster_peralatan_lainnya.append(parsed)
        else:
            if len(klaster_core_samples) < 50 and int(sku.replace("BBK", "")) % 60 == 0:
                klaster_core_samples.append(parsed)

        if parsed["missing_dimension"] and not parsed["is_non_product"]:
            klaster_missing_dim.append(parsed)
        if parsed["kondisi_tag"] == "Baru" or parsed["sub_komponen_baru"]:
            klaster_kondisi_baru.append(parsed)

    os.makedirs(os.path.dirname(WORKBENCH_PATH), exist_ok=True)
    with open(WORKBENCH_PATH, "w", encoding="utf-8") as f:
        f.write("# 🛠️ BBKitchen Comprehensive Catalog Audit & Review Workbench\n")
        f.write(f"> **Generated:** {time.strftime('%Y-%m-%d %H:%M:%S WIB')} | **SSOT Database:** `bbk.db` (`raw_pipeline`)\n")
        f.write(f"> **Total Catalog Data:** {total} SKUs | **Non-Product:** {len(klaster_non_product)} | **Low Confidence / Review:** {len(klaster_low_confidence)} | **Missing Dim:** {len(klaster_missing_dim)}\n\n")
        
        f.write("---\n\n")
        f.write("## 📖 PANDUAN CARA AUDIT & PENGISIAN WORKBENCH (UNTUK PRINCIPAL)\n\n")
        f.write("File ini dibuat khusus agar Sir dapat memeriksa langsung setiap unit anomali dengan mengklik **Link Telegram Asli** (melihat foto dan video unit), lalu menentukan keputusan dengan cepat:\n\n")
        f.write("1. **Cukup Centang / Tulis Keputusan:**\n")
        f.write("   - `[x] APPROVE` : Setujui hasil parsing regex apa adanya.\n")
        f.write("   - `[x] SKIP_NON_PRODUCT` : Tandai bukan produk horeca agar tidak masuk ke web publik / sitemap.\n")
        f.write("   - `[x] RE-AI` : Minta LLM AI Gateway untuk memproses ulang unit ini secara mendalam.\n")
        f.write("   - **Tulis Override** jika ingin mengganti Kategori / Judul / Dimensi secara manual pada kolom yang disediakan.\n")
        f.write("2. **Daftar Shortcut Kategori SSOT Utama (Tinggal Copy-Paste):**\n")
        f.write("   - `undercounter-chiller` | `upright-chiller` | `chiller` | `chest-freezer` | `upright-freezer` | `freezer`\n")
        f.write("   - `meja-1-susun-stainless` | `meja-2-susun-stainless` | `meja-3-susun-stainless` | `meja-kabinet-stainless` | `meja-kompor-stainless`\n")
        f.write("   - `single-sink-stainless` | `double-sink-stainless` | `triple-sink-stainless` | `sink-jumbo-stainless` | `lainnya-sink` (Grease Trap / Gutter)\n")
        f.write("   - `kompor-1-tungku` | `kompor-2-tungku` | `kompor-4-tungku` | `kompor-wok-kwali-range` | `kompor-grill-tepanyaki` | `deep-fryer` | `noodle-boiler` | `oven`\n")
        f.write("   - `rak-2-susun-stainless` | `rak-3-susun-stainless` | `rak-4-susun-stainless` | `rak-5-susun-stainless` | `wallshelf`\n")
        f.write("   - `showcase-1-pintu` | `showcase-2-pintu` | `cake-showcase` | `ice-maker` | `ice-bin`\n")
        f.write("   - `peralatan-dapur-bekas-lainnya` (Mixer, Meat Grinder, Slicer, Sealer, Juicer, Troli Bakery, dsb.)\n\n")
        f.write("---\n\n")

        # ======================================================================
        # SECTION 1: NON-PRODUCT (13 SKU)
        # ======================================================================
        f.write(f"## ⚪ 1. KLASTER NON-PRODUK / IKLAN / JASA ({len(klaster_non_product)} SKU)\n")
        f.write("> **Karakteristik:** Iklan loker besi, pengumuman ekspedisi J&T, mesin fotocopy, TV, cermin, patung andesit, atau penawaran jasa bengkel.\n")
        f.write("> **Rekomendasi:** Beri status `SKIP_NON_PRODUCT` agar katalog web publik steril.\n\n")

        for idx, item in enumerate(klaster_non_product, 1):
            tele_link = item['link_message']
            f.write(f"### {idx}. 📌 `[{item['sku']}]` {item['title']}\n")
            f.write(f"- 🔗 **Telegram Post:** [👉 Buka Post Telegram `{item['sku']}`]({tele_link})\n")
            f.write(f"- 📝 **Caption Asli:** `{item['caption_raw']}`\n")
            f.write(f"- 🤖 **Hasil Regex:** Kategori: `{item['category_slug']}` | Modal: `{format_rupiah(item['harga_modal'])}`\n")
            f.write(f"- ✍️ **Aksi Principal:**\n")
            f.write(f"  - [x] **SKIP_NON_PRODUCT** (Rekomendasi)\n")
            f.write(f"  - [ ] **JADIKAN PRODUK:** Kategori: `________________` | Judul: `________________`\n")
            f.write(f"  - [ ] **Catatan:** `________________________________________`\n\n")

        # ======================================================================
        # SECTION 2: LOW CONFIDENCE (116 SKU)
        # ======================================================================
        f.write("---\n\n")
        f.write(f"## 🟡 2. KLASTER BUTUH KLARIFIKASI KATEGORI / LOW CONFIDENCE ({len(klaster_low_confidence)} SKU)\n")
        f.write("> **Karakteristik:** Alat dapur cafe / mesin pengolah spesifik yang belum memuat kata kunci standar di kamus regex dasar.\n")
        f.write("> **Tugas Review:** Klik link Telegram, lihat foto unitnya, lalu centang atau tulis kategori SSOT yang sesuai.\n\n")

        for idx, item in enumerate(klaster_low_confidence, 1):
            tele_link = item['link_message']
            f.write(f"### {idx}. 📌 `[{item['sku']}]` {item['title']}\n")
            f.write(f"- 🔗 **Telegram Post:** [👉 Buka Post Telegram `{item['sku']}`]({tele_link})\n")
            f.write(f"- 📝 **Caption Asli:** `{item['caption_raw']}`\n")
            f.write(f"- 🤖 **Prediksi Regex:** Kategori: `{item['category_slug']}` | Dimensi: `{item['dimensi'] or 'N/A'}` | Modal: `{format_rupiah(item['harga_modal'])}`\n")
            f.write(f"- ✍️ **Keputusan & Klarifikasi Principal:**\n")
            f.write(f"  - [ ] **PILIH KATEGORI:** `[ ] peralatan-dapur-bekas-lainnya` | `[ ] kompor` | `[ ] chiller` | `[ ] meja-stainless` | `[ ] sink-stainless` | `[ ] rak-stainless`\n")
            f.write(f"  - [ ] **CUSTOM KATEGORI:** `____________________`\n")
            f.write(f"  - [ ] **OVERRIDE JUDUL:** `____________________`\n")
            f.write(f"  - [ ] **STATUS UNIT:** `[ ] READY` | `[ ] SOLD` | `[ ] SKIP_NON_PRODUCT`\n")
            f.write(f"  - [ ] **Catatan:** `________________________________________`\n\n")

        # ======================================================================
        # SECTION 3: STAINLESS MISSING DIMENSIONS (22 SKU)
        # ======================================================================
        f.write("---\n\n")
        f.write(f"## 📏 3. KLASTER UNIT STAINLESS TANPA ANGKA UKURAN ({len(klaster_missing_dim)} SKU)\n")
        f.write("> **Karakteristik:** Unit meja, sink, rak, atau hood yang caption Telegram-nya tidak menuliskan angka ukuran PxLxT cm.\n")
        f.write("> **Tugas Review:** Klik link Telegram untuk melihat foto fisik / taksiran ukuran jika diperlukan.\n\n")

        for idx, item in enumerate(klaster_missing_dim, 1):
            tele_link = item['link_message']
            f.write(f"### {idx}. 📌 `[{item['sku']}]` {item['title']}\n")
            f.write(f"- 🔗 **Telegram Post:** [👉 Buka Post Telegram `{item['sku']}`]({tele_link})\n")
            f.write(f"- 📝 **Caption Asli:** `{item['caption_raw']}`\n")
            f.write(f"- 🤖 **Kategori:** `{item['category_slug']}` | Modal: `{format_rupiah(item['harga_modal'])}`\n")
            f.write(f"- ✍️ **Input Dimensi Fisik (Jika Diketahui):**\n")
            f.write(f"  - [ ] **DIMENSI:** `____ x ____ x ____ cm` (Contoh: `120x70x85`)\n")
            f.write(f"  - [ ] **GUNAKAN STANDAR FALLBACK:** Biarkan judul tanpa dimensi `[{item['title']}]`\n\n")

        # ======================================================================
        # SECTION 4: KONDISI BARU / REFURBISHED (60 SKU)
        # ======================================================================
        f.write("---\n\n")
        f.write(f"## 🔍 4. KLASTER VERIFIKASI KONDISI 'BARU' VS KOMPONEN REFURBISHED ({len(klaster_kondisi_baru)} SKU)\n")
        f.write("> **Karakteristik:** Unit yang menyebutkan kata 'baru' di caption (apakah unit utuh baru sisa proyek vs hanya filter/kran/burner baru).\n\n")

        for idx, item in enumerate(klaster_kondisi_baru, 1):
            tele_link = item['link_message']
            sub_info = f"Komponen Baru: {item['sub_komponen_baru']}" if item['sub_komponen_baru'] else "Unit Baru Utuh"
            f.write(f"### {idx}. 📌 `[{item['sku']}]` {item['title']}\n")
            f.write(f"- 🔗 **Telegram Post:** [👉 Buka Post Telegram `{item['sku']}`]({tele_link})\n")
            f.write(f"- 📝 **Caption Asli:** `{item['caption_raw']}`\n")
            f.write(f"- 🤖 **Evaluasi Sistem:** Status: **`{item['kondisi_tag']}`** ({sub_info})\n")
            f.write(f"- ✍️ **Konfirmasi Principal:**\n")
            f.write(f"  - [x] **SETUJU** (Status `{item['kondisi_tag']}` sudah benar)\n")
            f.write(f"  - [ ] **UBAH JADI:** `[ ] Baru Sisa Proyek` | `[ ] Bekas Siap Pakai`\n\n")

        # ======================================================================
        # SECTION 5: MESIN OLAH MAKANAN & BAKERY (139 SKU - SAMPLE AUDIT)
        # ======================================================================
        f.write("---\n\n")
        f.write(f"## ⚙️ 5. KLASTER MESIN OLAH MAKANAN & BAKERY (VALID `peralatan-dapur-bekas-lainnya` — 139 SKU)\n")
        f.write("> **Karakteristik:** Mesin Mixer, Grinder, Slicer, Sealer, Juicer, Bone Saw, Troli Bakery yang telah berhasil dinormalisasi.\n\n")
        f.write("| No | SKU | Judul Bersih Terbentuk | Dimensi | Modal | Link Telegram Post |\n")
        f.write("| :---: | :---: | :--- | :---: | :---: | :---: |\n")
        for idx, item in enumerate(klaster_peralatan_lainnya, 1):
            f.write(f"| {idx} | **`{item['sku']}`** | {item['title']} | `{item['dimensi'] or '-'}` | `{format_rupiah(item['harga_modal'])}` | [Lihat Post ↗]({item['link_message']}) |\n")

    conn.close()
    print(f"✅ Workbench Generated Successfully at: {WORKBENCH_PATH}")

if __name__ == "__main__":
    generate_workbench()
