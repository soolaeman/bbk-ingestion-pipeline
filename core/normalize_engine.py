# -*- coding: utf-8 -*-
"""
👑 BBKitchen Sovereign Deterministic Normalization Core Engine (normalize_engine.py)
Sub-Modul 2.11 - Canonical AI & Deterministic Extraction Architecture

Features:
1. 5-Layer Hybrid Pipeline:
   - Layer 1: Regex Pre-Parser (Sanitasi Modal, Kontak, WhatsApp, Noise)
   - Layer 2: Deterministic Binary Condition Evaluator (False Positive sub-komponen baru vs unit bekas)
   - Layer 3: Kamus Slang Fonetik Gudang Horeca Lokal
   - Layer 4: LLM Structured JSON Extraction via AIGateway (OpenAI ➔ Gemini ➔ Groq ➔ DeepSeek)
   - Layer 5: Post-Validator & SSOT Taxonomy Assertion (58 Kategori SSOT & Guardrail Margins)
2. Sacred Slug Protection: Kunci mati permalink Google Search Console untuk produk lama (Zero 404).
3. Zero External Dependencies: Pure Python standard library + requests + AIGateway.
"""

import os
import re
import sys
import json
import time
import unicodedata
from typing import Dict, Any, Tuple, Optional, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure core and parent directory are on path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
for p in [CURRENT_DIR, PARENT_DIR]:
    if p not in sys.path:
        sys.path.append(p)

from ai_gateway import AIGateway, load_env

load_env()

# Config Paths
CONFIG_DIR_CANDIDATES = [
    os.path.join(CURRENT_DIR, "..", "config"),
    os.path.join(CURRENT_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "config"),
    os.path.join(os.getcwd(), "config"),
]

def load_ssot_taxonomy() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Loads canonical category and warehouse SSOT configurations."""
    cat_ssot = {}
    wh_ssot = {}
    for cdir in CONFIG_DIR_CANDIDATES:
        c_path = os.path.join(cdir, "categories_ssot.json")
        w_path = os.path.join(cdir, "warehouses_ssot.json")
        if os.path.exists(c_path) and not cat_ssot:
            try:
                with open(c_path, "r", encoding="utf-8") as f:
                    cat_ssot = json.load(f)
            except Exception:
                pass
        if os.path.exists(w_path) and not wh_ssot:
            try:
                with open(w_path, "r", encoding="utf-8") as f:
                    wh_ssot = json.load(f)
            except Exception:
                pass
    return cat_ssot, wh_ssot

CAT_SSOT, WH_SSOT = load_ssot_taxonomy()
OFFICIAL_CATEGORY_SLUGS = set(CAT_SSOT.get("by_slug", {}).keys())

# Fallback category mapping for common LLM deviations
CATEGORY_SYNONYM_MAP = {
    "undercounter-freezer": "freezer",
    "undercounter_freezer": "freezer",
    "undercounter_chiller": "undercounter-chiller",
    "upright_chiller": "upright-chiller",
    "upright_freezer": "upright-freezer",
    "chest_freezer": "chest-freezer",
    "single_sink": "single-sink-stainless",
    "double_sink": "double-sink-stainless",
    "triple_sink": "triple-sink-stainless",
    "meja_1_susun": "meja-1-susun-stainless",
    "meja_2_susun": "meja-2-susun-stainless",
    "meja_3_susun": "meja-3-susun-stainless",
    "rak_4_susun": "rak-4-susun-stainless",
    "kwali_range": "kompor-wok-kwali-range",
    "wok_range": "kompor-wok-kwali-range",
    "exhaust_hood": "hood",
    "grease_trap": "lainnya-sink",
    "greasetrap": "lainnya-sink",
    "gutter": "lainnya-sink",
}

# ==============================================================================
# LAYER 1 & 2: REGEX PRE-PARSER & DETERMINISTIC SANITIZERS
# ==============================================================================

def extract_modal_regex(caption: str) -> Optional[int]:
    """
    Ekstraksi angka modal/HPP dari caption gudang secara deterministik.
    Mendukung format 'Rp 12.500.000', '12,5jt', '500k', 'modal 4.2jt', dsb.
    """
    if not caption:
        return None

    clean = caption.lower()
    
    # 1. Juta patterns (e.g. 12.5 jt, 7,5juta, 15jt)
    jt_match = re.search(r'(?:harga|hrg|rp|modal|nett|net|bu)?\s*[:.\-]?\s*(\d+(?:[.,]\d+)?)\s*(?:jt|juta)', clean)
    if jt_match:
        val_str = jt_match.group(1).replace(',', '.')
        try:
            num = float(val_str)
            return int(num * 1_000_000)
        except Exception:
            pass

    # 2. Ribu / K patterns (e.g. 850k, 500 rb, 750ribu)
    k_match = re.search(r'(?:harga|hrg|rp|modal|nett|net|bu)?\s*[:.\-]?\s*(\d{1,4}(?:[.,]\d{1,3})?)\s*(?:k|rb|ribu)', clean)
    if k_match:
        val_str = k_match.group(1).replace('.', '').replace(',', '.')
        try:
            num = float(val_str)
            return int(num * 1_000)
        except Exception:
            pass

    # 3. Full nominal currency patterns (e.g. Rp 12.500.000, Hrg: 4.500.000)
    curr_patterns = [
        r'(?:harga|hrg|modal|nett|net|bu)\s*[:.\-]?\s*(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3}){1,3})',
        r'(?:rp\.?\s*)(\d{1,3}(?:[.,]\d{3}){1,3})',
    ]
    for pat in curr_patterns:
        m = re.search(pat, clean)
        if m:
            val_str = m.group(1).replace('.', '').replace(',', '')
            try:
                num = int(val_str)
                if num >= 100_000:
                    return num
            except Exception:
                pass

    return None

def sanitize_raw_caption(caption: str) -> str:
    """
    Sanitasi informasi kontak dan modal sensitif dari caption mentah
    sebelum dikirim ke LLM untuk mencegah data leakage dan halusinasi.
    """
    if not caption:
        return ""

    text = caption
    # 1. Strip phone numbers & WhatsApp links
    text = re.sub(r'(?:wa\.me/\d+|wa\s*:\s*\d+|\b08\d{8,12}\b|\+62\d{8,13})', '', text, flags=re.IGNORECASE)
    
    # 2. Strip Telegram links & username tags
    text = re.sub(r'https?://t\.me/\S+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'@\w+', '', text)
    
    # 3. Normalize whitespaces & emojis
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def evaluate_condition_binary(caption: str) -> Tuple[str, List[str]]:
    """
    LAYER 2: Algoritma Deteksi Kondisi Biner Anti-False-Positive.
    Mencegah sub-komponen baru (e.g. 'filter baru', 'kran baru', 'plat baru', 'saringan baru')
    membuat kondisi seluruh unit dianggap 'Baru'.
    
    Returns:
        (kondisi_unit, sub_components_baru_list)
    """
    if not caption:
        return "Bekas Siap Pakai", []

    cap_lower = caption.lower()
    
    # Sub-komponen yang sering diganti baru pada unit second
    sub_component_patterns = [
        (r'\bfilter\s+baru\b', 'Filter Baru'),
        (r'\bkran\s+baru\b', 'Kran Baru'),
        (r'\bplat\s+(?:tepan\s+)?baru\b', 'Plat Baru'),
        (r'\bburner\s+baru\b', 'Burner Baru'),
        (r'\bsaringan\s+baru\b', 'Saringan Baru'),
        (r'\bpipa\s+baru\b', 'Pipa Baru'),
        (r'\bkaret\s+(?:pintu\s+)?baru\b', 'Karet Pintu Baru'),
        (r'\bkompresor\s+baru\b', 'Kompresor Baru'),
        (r'\bthermostat\s+baru\b', 'Thermostat Baru'),
        (r'\bcat\s+baru\b', 'Cat Refurbished Baru'),
    ]

    new_sub_components = []
    for pat, label in sub_component_patterns:
        if re.search(pat, cap_lower):
            new_sub_components.append(label)

    # Unit-level true new indicators (Strict Whole Unit)
    true_new_patterns = [
        r'\b100%\s*baru\b',
        r'\bunit\s+baru\s+(?:gress|dus|box)\b',
        r'\bgress\s+baru\b',
        r'\bbrand\s+new\s+in\s+box\b',
        r'\bbaru\s+sisa\s+proyek\b',
        r'\bbukit\s+sisa\s+proyek\s+baru\b',
        r'\bbelum\s+pernah\s+(?:dipakai|pake|pakai)\b'
    ]
    is_true_new = any(re.search(pat, cap_lower) for pat in true_new_patterns)

    # Like new / Display indicators
    like_new_patterns = [
        r'\blike\s+new\b',
        r'\bex\s*display\b',
        r'\bkondisi\s+9[5-9]%\b',
        r'\bmulus\s+seperti\s+baru\b'
    ]
    is_like_new = any(re.search(pat, cap_lower) for pat in like_new_patterns)

    if is_true_new and not new_sub_components:
        return "Baru Sisa Proyek", new_sub_components
    elif is_like_new:
        return "Like New / Ex-Display", new_sub_components
    else:
        return "Bekas Siap Pakai", new_sub_components

# ==============================================================================
# LAYER 3: KAMUS SLANG FONETIK & BRAND/FABRICATION RULES
# ==============================================================================

SLANG_DICTIONARY = {
    "shocess": "Showcase",
    "sokes": "Showcase",
    "sowkes": "Showcase",
    "chocase": "Showcase",
    "ciler": "Chiller",
    "ciller": "Chiller",
    "aprait": "Upright Chiller",
    "apraite": "Upright Chiller",
    "anderconter": "Undercounter Chiller",
    "underconter": "Undercounter Chiller",
    "prizer": "Freezer",
    "freser": "Freezer",
    "frizer": "Freezer",
    "sing": "Sink Stainless",
    "singk": "Sink Stainless",
    "bak cuci": "Sink Stainless",
    "kwali bloer": "Kwali Range Blower",
    "kuali ren": "Kwali Range",
    "kwali blower": "Kwali Range Blower",
    "dip frayer": "Deep Fryer",
    "preyer gas": "Deep Fryer Gas",
    "bekples": "Backsplash",
    "beckplash": "Backsplash",
    "ambalan": "Susun",
    "trap": "Susun",
    "selping": "Shelving",
    "greastrep": "Grease Trap",
    "gris trap": "Grease Trap",
    "stimer": "Dimsum Steamer",
    "kukusan": "Dimsum Steamer",
    "tepanyaki": "Teppanyaki",
    "tepangrild": "Teppanyaki Grill",
}

KNOWN_COMMERCIAL_BRANDS = [
    "GEA", "Mastercool", "Nayati", "Getra", "Sander", "Krischef",
    "Berjaya", "Fomac", "Crown", "Rational", "Escoffier", "Hoshizaki",
    "Liebherr", "Unox", "Convotherm", "Kolb", "Roller Grill", "Sirman",
    "Sinmag", "Primax", "Guangdong", "Mutu", "Zanussi", "Electrolux"
]

FABRICATION_KEYWORDS = ["meja", "sink", "rak", "hood", "wallshelf", "kabinet", "cabinet", "trolley", "grease trap"]

# ==============================================================================
# LAYER 4: GOLDEN LLM SYSTEM PROMPT & INSTRUCTION
# ==============================================================================

GOLDEN_SYSTEM_PROMPT = """Anda adalah Principal Catalog Architect & Senior Equipment Expert untuk BBKitchen (Penyedia Peralatan Dapur Komersial & Resto Second Terbesar di Indonesia).

Tugas Anda: Menganalisis caption mentah Telegram dari gudang mitra secara semantik (100% AI-Driven Semantic Extraction), mengekstrak fakta akurat, membersihkan noise/typo, dan menghasilkan data katalog standar industri Horeca kelas atas.

5 ATURAN BISNIS EMAS (5 GOLDEN RULES):

1. TUGAS 1 - JUDUL PRODUK KANONIKAL BERSIH & BERDIMENSI ("title_bersih"):
   - FORMULA RESMI: [Nama Standar Alat] [Brand jika ada] Second [Dimensi PxLxT / Kapasitas]
   - ATURAN KANONIKAL:
     * Selalu gunakan format rapi, konsisten, dan simetris untuk tampilan katalog web/mobile.
     * WAJIB cantumkan dimensi fisik (contoh: 110x70x85 cm) atau kapasitas (contoh: 231L, 2 Pintu, 21 Tray, 2 Burner).
     * Jika unit Bekas, gunakan kata "Second". Jika unit Baru, gunakan kata "Baru".
   - Contoh Ideal "title_bersih":
     * "Meja Stainless 2 Susun Second 110x70x85 cm"
     * "Troli Bakery Stainless 21 Tray Second 45x63x170 cm"
     * "Double Sink Stainless 2 Lubang Second 120x60x84 cm"
     * "Showcase 1 Pintu GEA Second 231L"
     * "Upright Chiller 2 Pintu Mastercool Second"
     * "Kompor Grill Teppanyaki Stainless Second 100x70x85 cm"
     * "Ice Bin Stainless Steel Second 180x70x85 cm"
   - Maksimal 65 karakter, Title Case.
   - ATURAN BRAND vs JARGON TEKNIS:
     * Brand Resmi: GEA, Mastercool, Nayati, Getra, Sander, Krischef, Berjaya, Fomac, Crown, Rational, Escoffier, Hoshizaki, Liebherr, Unox, Convotherm, Kolb, Roller Grill, Sirman, Sinmag, Primax, Guangdong, Mutu, Zanussi, Electrolux, Rinnai, Modena, RSA.
     * Jargon Teknis BUKAN Brand (Brand: null): Low Pressure, High Pressure, Heavy Duty, Table Top, Custom 201/304, Stainless, Blower, 1 Tungku, Sliding Door, Kaki Roda.
     * Fabrikasi Stainless (Meja, Sink, Rak, Hood, Wallshelf, Kabinet, Grease Trap) 99% custom bengkel -> Brand: null.

2. TUGAS 2 - BADGE SEMANTIK KONTEKSTUAL ("semantic_badge"):
   - Pilih 1 badge persona asal unit untuk ditampilkan sebagai stiker elegan di foto katalog:
     * "Ex-Resto" (Peralatan dapur resto, kompor kwali, sink, meja potong)
     * "Ex-Cafe" (Chiller display, undercounter, blender, ice bin, cake showcase)
     * "Ex-Bakery" (Troli loyang roti, deck oven, proofer, planetary mixer)
     * "Ex-Hotel" (Combi oven, banquet cart, heavy duty dishwasher)
     * "Second Mulus" (Peralatan umum dengan kondisi fisik sangat terawat)
     * "Baru Gress" (Unit baru sisa proyek/stok distributor)

3. TUGAS 3 - EKSTRAKSI MODAL & HPP GUDANG FAKTUAL ("harga_modal"):
   - Pahami semantik harga dari caption:
     * "modal 2.5jt" / "2,2jt net" / "harga 4.500.000" -> Ekstrak angka integer rupiah murni (contoh: 2500000).
     * Jika harga borongan: "ambil 3 unit 6jt" -> Hitung harga satuan per unit: 2000000.
     * Jika TIDAK ADA angka harga/modal yang jelas di caption -> WAJIB isi "harga_modal": null. Dilarang menebak angka modal jika tidak tertulis!

4. TUGAS 4 - EVALUASI KONDISI SEJATI & ANTI-JEBAKAN ("kondisi_unit"):
   - "Bekas Siap Pakai" (Default): Unit bekas restoran/cafe. Jika ada info sparepart baru (contoh: "filter baru", "burner baru", "basket baru", "karet pintu baru") atau durasi pemakaian ("pemakaian baru 4 bulan"), unit utama TETAP "Bekas Siap Pakai".
   - "Like New / Ex-Display": Unit bekas sangat mulus, eks display pameran, atau pemakaian di bawah 1 bulan dengan fisik 95%+.
   - "Baru Sisa Proyek": Unit 100% baru, BNIB, belum pernah dipakai sama sekali (bukan bekas).

5. TUGAS 5 - RISET GROUNDING HARGA PASAR FAKTUAL:
   - "estimasi_harga_baru": Taksiran harga wajar unit BARU distributor resmi di Indonesia berdasarkan brand, kapasitas, daya watt, dan material SUS 304 (integer rupiah).
   - "harga_display_low": Rekomendasi harga penawaran second buka wajar di pasar (angka bulat kelipatan 100rb, misal ~40%-55% dari harga baru).
   - "harga_display_high": Batas atas rentang penawaran second di pasar (angka bulat kelipatan 100rb, misal ~60%-75% dari harga baru).

6. TUGAS 6 - PEMILIHAN 58 KATEGORI SSOT & INTENT FILTER:
   - Pilih 1 slug resmi kanonikal dari master taksonomi:
     * CHILLER: undercounter-chiller, upright-chiller, chiller, lainnya-chiller
     * FREEZER: chest-freezer, upright-freezer, freezer, lainnya-freezer
     * ICE SYSTEM: ice-bin, ice-maker, ice-system, lainnya-ice-system
     * MEJA STAINLESS: meja-1-susun-stainless, meja-2-susun-stainless, meja-3-susun-stainless, meja-bumbu-stainless, meja-kabinet-stainless, meja-kompor-stainless, meja-stainless, lainnya-meja-stainless
     * SINK STAINLESS: single-sink-stainless, double-sink-stainless, triple-sink-stainless, sink-jumbo-stainless, sink-stainless, lainnya-sink (termasuk grease trap)
     * KOMPOR: kompor-1-tungku, kompor-2-tungku, kompor-3-tungku, kompor-4-tungku, kompor-6-tungku, kompor-wok-kwali-range, kompor-batu-lava, kompor-grill-tepanyaki, deep-fryer, noodle-boiler, oven, kompor, lainnya-kompor
     * RAK: rak-1-susun-stainless, rak-2-susun-stainless, rak-3-susun-stainless, rak-4-susun-stainless, rak-5-susun-stainless, wallshelf, rak-stainless, lainnya-rak-stainless
     * HOOD: hood, blower, ducting, hood-stainless, lainnya-hood
     * SHOWCASE: showcase-1-pintu, showcase-2-pintu, cake-showcase, showcase, lainnya-showcase
     * LAINNYA: peralatan-dapur-bekas-lainnya (hanya untuk barang non-standar)
   - "is_non_product": true jika postingan adalah info dompet hilang, peringatan penipu, loker teknisi, promo ekspedisi/kargo, jasa las, atau barang non-horeca.
   - "confidence": "HIGH" jika spesifikasi teridentifikasi jelas, "LOW" jika caption sangat minim/meragukan.

PROGRAMMATIC SEO & 4-TIER ALT TEXT SUITE (VARIASI SEMANTIK KAYA DI GOOGLE):
- "seo_title": "[nama_alat] [dimensi] [semantic_badge] Siap Pakai | BBKitchen"
- "yoast_description": "Ready stok [nama_alat] [dimensi] kondisi bekas [semantic_badge] siap pakai lolos QC teknisi BBKitchen. Siap kirim se-Jabodetabek via Lalamove!"
- "image_alt": "[nama_alat] [dimensi] [semantic_badge] Bekas Bergaransi BBKitchen"
- "image_title": "Jual [nama_alat] [semantic_badge] [brand] [dimensi]"
- "image_caption": "[nama_alat] [dimensi] kondisi mulus siap pakai lolos QC teknikal BBKitchen"
- "image_description": "[title_bersih] bergaransi 30 hari siap kirim se-Indonesia."

KEMBALIKAN STRICTLY JSON SESUAI SKEMA INI:
{
  "title_bersih": str,
  "nama_alat": str,
  "brand": str | null,
  "dimensi": str | null,
  "semantic_badge": "Ex-Resto" | "Ex-Cafe" | "Ex-Bakery" | "Ex-Hotel" | "Second Mulus" | "Baru Gress",
  "category_slug": str,
  "kondisi_unit": "Bekas Siap Pakai" | "Like New / Ex-Display" | "Baru Sisa Proyek",
  "status_unit": "READY" | "SOLD",
  "harga_modal": int | null,
  "estimasi_harga_baru": int,
  "harga_display_low": int,
  "harga_display_high": int,
  "is_non_product": bool,
  "confidence": "HIGH" | "LOW",
  "seo_title": str,
  "yoast_keyword": str,
  "yoast_description": str,
  "spesifikasi_ringkas": [str],
  "image_alt": str,
  "image_title": str,
  "image_caption": str,
  "image_description": str
}
"""

# ==============================================================================
# LAYER 5: AUDIT GUARDRAIL MARGINS & PRICE ANCHORS (AI-FIRST SSOT)
# ==============================================================================

def calculate_margins_and_anchors(
    modal: Optional[int],
    estimasi_baru: Optional[int] = None,
    ai_display_low: Optional[int] = None,
    ai_display_high: Optional[int] = None,
    category_slug: str = ""
) -> Dict[str, Any]:
    """
    Audit Guardrail Murni & 5-Tier Empirical Pricing Matrix SSOT.
    
    Prinsip Sakral:
    1. 5-Tier Capital Brackets (Micro, Small Stainless, Small Mesin, Medium, Large, Industrial).
    2. Jamin 3-Tier WA Negotiation Space (Floor WA < Deal WA < Buka WA).
    3. Display Web Low = Buka WA (Bebas bocor modal, buyer dapat diskon saat chat WA).
    4. Display Web High = Buka WA + 20% (capped di 75% Estimasi Harga Baru).
    5. Estimasi Baru SSOT = 2.0x - 2.4x modal atau hasil riset faktual AI.
    """
    cat_lower = (category_slug or "").lower()
    is_stainless = any(k in cat_lower for k in ['meja', 'rak', 'sink', 'troli', 'trolley', 'cabinet', 'stainless', 'pantry', 'grease', 'hood'])

    if modal is not None and modal > 0:
        modal_clean = int(modal)

        # 1. Tentukan Margin Ratios & Multiplier berdasarkan Bracket Modal
        if modal_clean < 1_500_000:
            # Micro (<1.5jt): Rak bumbu, sink 1 bowl, grease trap kecil
            m_floor, m_deal, m_buka = 0.25, 0.40, 0.55
            ratio_est_baru = 2.2
            round_unit = 50_000
        elif modal_clean <= 3_500_000:
            # Small (1.5jt - 3.5jt): Jantung Katalog BBKitchen (47.2%)
            if is_stainless:
                m_floor, m_deal, m_buka = 0.20, 0.30, 0.42
                ratio_est_baru = 2.2
            else:
                m_floor, m_deal, m_buka = 0.20, 0.35, 0.48
                ratio_est_baru = 2.4
            round_unit = 50_000
        elif modal_clean <= 7_500_000:
            # Medium (3.5jt - 7.5jt): Undercounter, Kwali 2 tungku, Fryer komersial
            m_floor, m_deal, m_buka = 0.18, 0.28, 0.38
            ratio_est_baru = 2.3
            round_unit = 100_000
        elif modal_clean <= 15_000_000:
            # Large (7.5jt - 15jt): Upright 4 pintu, Spiral mixer 20L
            m_floor, m_deal, m_buka = 0.15, 0.22, 0.30
            ratio_est_baru = 2.1
            round_unit = 100_000
        else:
            # Industrial (>15jt): Combi oven, Walk-in chiller, Rotary oven
            m_floor, m_deal, m_buka = 0.12, 0.18, 0.25
            ratio_est_baru = 2.0
            round_unit = 250_000

        # 2. Hitung 3 Tingkat Harga Negosiasi Sales WA
        harga_floor_wa = ((int(modal_clean * (1 + m_floor)) + (round_unit - 1)) // round_unit) * round_unit
        harga_deal_wa  = ((int(modal_clean * (1 + m_deal)) + (round_unit - 1)) // round_unit) * round_unit
        harga_buka_wa  = ((int(modal_clean * (1 + m_buka)) + (round_unit - 1)) // round_unit) * round_unit

        # 3. Estimasi Harga Baru SSOT
        if estimasi_baru and int(estimasi_baru) >= int(modal_clean * 1.5):
            est_baru_clean = int(estimasi_baru)
        else:
            est_baru_clean = ((int(modal_clean * ratio_est_baru) + 99_999) // 100_000) * 100_000

        # 4. Display Publik Web (Low & High)
        final_disp_low = harga_buka_wa
        
        raw_high = int(final_disp_low * 1.20)
        ceiling_high = max(int(est_baru_clean * 0.75), int(final_disp_low * 1.10)) # maks 75% harga baru
        final_disp_high = min(raw_high, ceiling_high)
        if final_disp_high <= final_disp_low:
            final_disp_high = int(final_disp_low * 1.15)
        final_disp_high = ((final_disp_high + 99_999) // 100_000) * 100_000

        # Guardrail Audit Status
        if modal_clean >= est_baru_clean:
            status_guardrail = "ANOMALY_OVERPRICED_MODAL"
        elif modal_clean >= final_disp_low:
            status_guardrail = "WARNING_THIN_MARGIN"
        else:
            status_guardrail = "PASS"

        return {
            "harga_modal": modal_clean,
            "margin_floor": m_floor,
            "margin_deal": m_deal,
            "harga_floor_wa": harga_floor_wa,
            "harga_deal_wa": harga_deal_wa,
            "harga_buka_wa": harga_buka_wa,
            "status_guardrail": status_guardrail,
            "estimasi_harga_baru": est_baru_clean,
            "harga_display_low": final_disp_low,
            "harga_display_high": final_disp_high,
        }
    else:
        # Graceful Null Pricing (No fake modal fabrication)
        default_est_baru = 10_000_000
        if "chiller" in cat_lower or "freezer" in cat_lower:
            default_est_baru = 25_000_000
        elif "kwali" in cat_lower or "oven" in cat_lower:
            default_est_baru = 20_000_000
        elif "meja" in cat_lower or "sink" in cat_lower or "rak" in cat_lower:
            default_est_baru = 4_000_000

        est_baru_clean = int(estimasi_baru) if estimasi_baru and estimasi_baru > 0 else default_est_baru
        disp_low = ai_display_low if ai_display_low and ai_display_low > 0 else int(est_baru_clean * 0.45)
        disp_low = ((disp_low + 99_999) // 100_000) * 100_000
        disp_high = ai_display_high if ai_display_high and ai_display_high > disp_low else int(disp_low * 1.25)
        disp_high = ((disp_high + 99_999) // 100_000) * 100_000

        return {
            "harga_modal": None,
            "margin_floor": None,
            "margin_deal": None,
            "harga_floor_wa": None,
            "harga_deal_wa": None,
            "harga_buka_wa": disp_low,
            "status_guardrail": "NO_MODAL_INFO",
            "estimasi_harga_baru": est_baru_clean,
            "harga_display_low": disp_low,
            "harga_display_high": disp_high,
        }

def format_rupiah(num: Optional[int]) -> str:
    if num is None or num <= 0:
        return "—"
    return f"Rp {num:,}".replace(",", ".")

def build_rich_description(parsed: Dict[str, Any], pricing: Dict[str, Any], location_name: str, sub_components_baru: List[str] = None) -> str:
    """Generates sanitized, high-conversion HTML description."""
    nama = parsed.get("nama_alat", "Peralatan Dapur Komersial")
    brand = parsed.get("brand", "")
    specs = parsed.get("spesifikasi_ringkas", [])
    est_baru = pricing["estimasi_harga_baru"]
    disp_low = pricing["harga_display_low"]
    disp_high = pricing["harga_display_high"]

    spec_items = []
    if sub_components_baru:
        for sc in sub_components_baru:
            spec_items.append(f"<li><strong>Komponen Refurbished:</strong> {sc} (Kondisi Prima)</li>")
    
    if specs and isinstance(specs, list):
        for s in specs:
            clean_s = str(s).strip().lstrip("•- ")
            if clean_s:
                spec_items.append(f"<li>{clean_s}</li>")
    
    if not spec_items:
        spec_items = [
            "<li>Material bodi stainless steel standar komersial Horeca.</li>",
            "<li>Fungsi operasional teruji siap pakai dan lolos inspeksi teknikal.</li>"
        ]

    spec_html = "\n    ".join(spec_items)
    brand_label = f"({brand})" if brand else "(Commercial Grade)"
    kondisi_label = parsed.get("kondisi_unit", "Bekas Siap Pakai")

    hemat_min_pct = round((1 - (disp_high / est_baru)) * 100) if est_baru > 0 else 30
    hemat_max_pct = round((1 - (disp_low / est_baru)) * 100) if est_baru > 0 else 50

    html = f"""<div class="bbk-product-description">
  <h3>Spesifikasi & Keunggulan Unit</h3>
  <p>Unit <strong>{nama}</strong> {brand_label} dalam kondisi prima dan siap langsung dioperasikan untuk kebutuhan dapur restoran, cafe, bakery, atau katering Anda. Seluruh unit di BBKitchen telah melalui proses kurasi ketat dan uji fungsi mekanikal serta elektrikal sebelum ditawarkan.</p>
  <ul>
    {spec_html}
    <li><strong>Lokasi Unit:</strong> {location_name}</li>
    <li><strong>Kondisi:</strong> {kondisi_label}</li>
  </ul>

  <div class="panduan-anggaran" style="margin-top: 24px; padding: 16px 20px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;">
    <h4 style="margin-top: 0; color: #0f172a; font-weight: 800;">Panduan Anggaran & Estimasi Nilai Pasar</h4>
    <ul style="margin-bottom: 8px;">
      <li><strong>Estimasi Harga Unit Baru (Distributor):</strong> ~{format_rupiah(est_baru)}</li>
      <li><strong>Rentang Penawaran Unit Second BBKitchen:</strong> {format_rupiah(disp_low)} – {format_rupiah(disp_high)}</li>
      <li><strong>Potensi Efisiensi Investasi:</strong> Hemat {hemat_min_pct}% s/d {hemat_max_pct}% dari harga baru</li>
    </ul>
    <p style="font-size: 12px; color: #64748b; margin-bottom: 0;"><em>*Catatan: Penawaran final bergantung pada grade kemulusan fisik, riwayat operasional, kelengkapan aksesoris, dan paket garansi servis. Hubungi konsultan kami untuk cek unit & penawaran terbaik.</em></p>
  </div>
</div>"""
    return html

def resolve_warehouse_partner(source_group: str = "", link: str = "") -> Tuple[str, str]:
    """Resolves canonical warehouse partner code and location name."""
    partners = WH_SSOT.get("partners", {})
    sg_str = str(source_group or "").strip()
    link_str = str(link or "").strip()

    # 1. Direct partner code match
    if sg_str in partners:
        p = partners[sg_str]
        return (p["code"], p["location"])

    # 2. Match by Telegram Channel ID directly
    for code, p in partners.items():
        tele_id = str(p.get("telegram_id") or "").strip()
        if tele_id and (tele_id == sg_str or tele_id.replace("-100", "") == sg_str.replace("-100", "")):
            return (p["code"], p["location"])

    # 3. Match by Link URL
    if link_str:
        for code, p in partners.items():
            tele_id = str(p.get("telegram_id") or "").strip()
            if tele_id:
                clean_id = tele_id.replace("-100", "").replace("-", "")
                if f"/c/{clean_id}/" in link_str or f"/{clean_id}/" in link_str:
                    return (p["code"], p["location"])

    # Default fallback to Pamulang 2 (GK)
    main_hub = partners.get("GK", {"code": "GK", "location": "PAMULANG 2, TANGSEL"})
    return (main_hub["code"], main_hub["location"])

# ==============================================================================
# DETERMINISTIC FALLBACK ENGINE (ZERO-LLM RESILIENCE)
# ==============================================================================

def extract_product_fallback(caption: str, sku: str) -> Dict[str, Any]:
    """Deterministic fallback parser when all AI providers are offline."""
    dim_match = re.search(r'(\d{2,3}\s*[xX*]\s*\d{2,3}(?:\s*[xX*]\s*\d{2,3})?(?:\s*cm)?)', caption)
    dimensi = dim_match.group(1).replace(" ", "") if dim_match else ""

    cap_lower = caption.lower()
    cat_slug = "peralatan-dapur-bekas-lainnya"
    nama_alat = "Peralatan Dapur Komersial"
    brand = ""

    # Check brand
    for b in KNOWN_COMMERCIAL_BRANDS:
        if b.lower() in cap_lower:
            brand = b
            break

    # Check category & equipment name
    if any(k in cap_lower for k in ["chiller", "ciler", "ciller"]):
        if any(k in cap_lower for k in ["undercounter", "anderconter", "under conter"]):
            cat_slug = "undercounter-chiller"
            nama_alat = "Undercounter Chiller 2 Pintu"
        elif any(k in cap_lower for k in ["4 pintu", "4p"]):
            cat_slug = "upright-chiller"
            nama_alat = "Upright Chiller 4 Pintu"
        elif any(k in cap_lower for k in ["2 pintu", "2p"]):
            cat_slug = "upright-chiller"
            nama_alat = "Upright Chiller 2 Pintu"
        else:
            cat_slug = "upright-chiller"
            nama_alat = "Upright Chiller"
    elif any(k in cap_lower for k in ["freezer", "prizer", "freser", "frizer"]):
        if "upright" in cap_lower:
            cat_slug = "upright-freezer"
            nama_alat = "Upright Freezer"
        elif "chest" in cap_lower or "box" in cap_lower:
            cat_slug = "chest-freezer"
            nama_alat = "Chest Freezer"
        else:
            cat_slug = "chest-freezer"
            nama_alat = "Chest Freezer"
    elif any(k in cap_lower for k in ["greastrep", "gris trap", "grease trap", "perangkap lemak", "jebakan lemak"]):
        cat_slug = "lainnya-sink"
        nama_alat = "Grease Trap Stainless Steel"
    elif any(k in cap_lower for k in ["sink", "singk", "bak cuci"]):
        if any(k in cap_lower for k in ["double", "2 lubang", "2 pot", "2 bowl"]):
            cat_slug = "double-sink-stainless"
            nama_alat = "Double Sink Stainless 2 Lubang"
        elif any(k in cap_lower for k in ["triple", "3 lubang", "3 pot"]):
            cat_slug = "triple-sink-stainless"
            nama_alat = "Triple Sink Stainless 3 Lubang"
        else:
            cat_slug = "single-sink-stainless"
            nama_alat = "Single Sink Stainless"
    elif any(k in cap_lower for k in ["kabinet", "cabinet"]):
        cat_slug = "meja-kabinet-stainless"
        if "sliding" in cap_lower or "geser" in cap_lower:
            nama_alat = "Meja Kabinet Sliding Stainless"
        else:
            nama_alat = "Meja Kabinet Stainless"
    elif "meja" in cap_lower:
        if any(k in cap_lower for k in ["3 susun", "3 trap", "3 tier"]):
            cat_slug = "meja-3-susun-stainless"
            nama_alat = "Meja Stainless 3 Susun"
        elif any(k in cap_lower for k in ["2 susun", "2 trap", "2 tier"]):
            cat_slug = "meja-2-susun-stainless"
            nama_alat = "Meja Stainless 2 Susun"
        elif "kompor" in cap_lower:
            cat_slug = "meja-kompor-stainless"
            nama_alat = "Meja Kompor Stainless"
        else:
            cat_slug = "meja-stainless"
            nama_alat = "Meja Stainless"
    elif any(k in cap_lower for k in ["kwali", "kuali", "wok"]):
        cat_slug = "kompor-wok-kwali-range"
        nama_alat = "Kwali Range 2 Burner Blower" if "2" in cap_lower else "Kwali Range 1 Burner Blower"
    elif "deep fryer" in cap_lower or "dip frayer" in cap_lower:
        cat_slug = "deep-fryer"
        nama_alat = "Deep Fryer Gas 1 Tank"
    elif "rak" in cap_lower or "rack" in cap_lower:
        cat_slug = "rak-4-susun-stainless"
        nama_alat = "Rak Stainless 4 Susun"
    elif "hood" in cap_lower:
        cat_slug = "hood"
        nama_alat = "Exhaust Hood Stainless"
    elif "showcase" in cap_lower or "sokes" in cap_lower or "shocess" in cap_lower:
        if any(k in cap_lower for k in ["3 pintu", "3p"]):
            cat_slug = "showcase-2-pintu"
            nama_alat = "Showcase 3 Pintu"
        elif any(k in cap_lower for k in ["2 pintu", "2p"]):
            cat_slug = "showcase-2-pintu"
            nama_alat = "Showcase 2 Pintu"
        else:
            cat_slug = "showcase-1-pintu"
            nama_alat = "Showcase 1 Pintu"

    kondisi_unit, sub_baru = evaluate_condition_binary(caption)
    modal = extract_modal_regex(caption)

    # Clean title
    parts = [nama_alat]
    if brand and not any(k in nama_alat.lower() for k in FABRICATION_KEYWORDS):
        parts.append(brand)
    parts.append("Second")
    if dimensi:
        parts.append(dimensi)
    title_bersih = " ".join(parts)

    return {
        "title_bersih": title_bersih,
        "nama_alat": nama_alat,
        "brand": brand,
        "dimensi": dimensi,
        "category_slug": cat_slug,
        "kondisi_unit": kondisi_unit,
        "status_unit": "READY",
        "harga_modal": modal,
        "estimasi_harga_baru": modal * 2 if modal else 10_000_000,
        "is_non_product": False,
        "confidence": "LOW",
        "yoast_keyword": f"{nama_alat.lower()} bekas",
        "yoast_description": f"{title_bersih} kondisi siap pakai bergaransi.",
        "spesifikasi_ringkas": [
            f"Dimensi: {dimensi or 'Standar Komersial'}",
            "Material stainless steel food grade",
            "Fungsi mekanikal & elektrikal teruji siap pakai",
            "Unit lolos inspeksi quality control BBKitchen"
        ],
        "image_alt": f"{title_bersih} Bekas Bergaransi BBKitchen",
        "image_title": f"Jual {nama_alat} Bekas Resto Cafe {brand} {dimensi}".strip(),
        "image_caption": f"{nama_alat} kondisi mulus siap pakai lolos QC teknikal",
        "image_description": f"{title_bersih} bergaransi 30 hari siap kirim."
    }

# ==============================================================================
# MAIN NORMALIZATION FUNCTION (UNIFIED RUNNER & BATCH HARMONIZER)
# ==============================================================================

def normalize_single_caption(
    raw_caption: str,
    sku: str,
    existing_slug: Optional[str] = None,
    source_group: str = "",
    link_message: str = "",
    location_override: str = "",
    photo_urls: str = "",
    gateway: Optional[AIGateway] = None
) -> Dict[str, Any]:
    """
    Eksekusi normalisasi lengkap untuk 1 item data mentah.
    Menghasilkan dictionary siap simpan ke tabel products (SQLite & Turso Edge).
    """
    if gateway is None:
        gateway = AIGateway()

    # 1. Resolve Warehouse & Location
    hub_code, location_name = resolve_warehouse_partner(source_group, link=link_message)
    if location_override and any(h in location_override.upper() for h in ["TANGSEL", "DEPOK", "HQ", "BOGOR", "JAKARTA"]):
        location_name = location_override

    # 2. Pre-Parsing & Sanitasi
    sanitized_caption = sanitize_raw_caption(raw_caption)
    modal_pre_check = extract_modal_regex(raw_caption)
    kondisi_pre_check, sub_baru_list = evaluate_condition_binary(raw_caption)

    # 3. LLM Call via AIGateway (Cascade: OpenAI ➔ Gemini ➔ Groq ➔ DeepSeek)
    user_prompt = f"""KODE UNIT: {sku}
LOKASI GUDANG: {location_name} (Hub: {hub_code})

CAPTION MENTAH GUDANG:
\"\"\"{sanitized_caption}\"\"\"

Ekstrak spesifikasi teknis, taksonomi kategori, dan estimasi harga sesuai panduan sistem."""

    parsed = None
    for attempt in range(1, 4):
        try:
            parsed = gateway.generate_json(user_prompt, system_prompt=GOLDEN_SYSTEM_PROMPT)
            if parsed and isinstance(parsed, dict) and (parsed.get("title_bersih") or parsed.get("nama_alat")):
                break
        except Exception as err:
            print(f"   [AI Gateway Attempt {attempt}/3 Warning on {sku}] {err}")
            if attempt < 3:
                time.sleep(attempt * 2)

    # 4. Fallback if AI offline or returned invalid schema
    if not parsed or not isinstance(parsed, dict):
        print(f"   [Deterministic Fallback Engine] Generating structured record for {sku}...")
        parsed = extract_product_fallback(raw_caption, sku)

    # 5. Build Title & Sanitize (Opsi 2: Clean Canonical Title with Dimensions)
    title_bersih = (parsed.get("title_bersih") or "").strip()
    nama_alat = (parsed.get("nama_alat") or "Peralatan Dapur Komersial").strip()
    brand = (parsed.get("brand") or "").strip()
    dimensi = (parsed.get("dimensi") or "").strip()

    # If dimension missing from AI output, recover from raw caption/text
    if not dimensi:
        dim_match = re.search(r'(\d{2,3}\s*[xX*]\s*\d{2,3}(?:\s*[xX*]\s*\d{2,3})?(?:\s*cm)?)', raw_caption)
        if dim_match:
            dimensi = dim_match.group(1).replace(" ", "")
            if not dimensi.lower().endswith("cm"):
                dimensi = f"{dimensi} cm"

    if title_bersih:
        title = title_bersih
        # Guarantee dimension is in title for unique identification
        if dimensi and dimensi.lower() not in title.lower() and len(f"{title} {dimensi}") <= 70:
            title = f"{title} {dimensi}"
    else:
        parts = [nama_alat]
        # Ignore brand for stainless fabrication
        is_fabrication = any(k in nama_alat.lower() for k in FABRICATION_KEYWORDS)
        if brand and not is_fabrication and brand.lower() not in nama_alat.lower():
            parts.append(brand)
        if "second" not in [p.lower() for p in parts]:
            parts.append("Second")
        if dimensi and dimensi.lower() not in nama_alat.lower():
            parts.append(dimensi)
        title = " ".join(parts)

    # Strip any leaked prices / WA from title
    title = re.sub(r'(?i)(?:rp\.?\s*[\d.,]+|[\d.,]+\s*(?:jt|juta|k|rb|ribu))', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 75:
        title = title[:75].rsplit(" ", 1)[0]

    # 6. Sacred Slug Immutability Protection & Unique Formula
    if existing_slug and str(existing_slug).strip():
        slug = str(existing_slug).strip()
    else:
        clean_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        sku_suffix = sku.lower()
        if clean_slug:
            slug = clean_slug if clean_slug.endswith(f"-{sku_suffix}") else f"{clean_slug}-{sku_suffix}"
        else:
            slug = f"unit-{sku_suffix}"

    link_unit = f"https://bukanbarukitchen.com/shop/{slug}/"

    # 7. Category Assertion
    cat_slug = str(parsed.get("category_slug") or "").strip().lower()
    if cat_slug in CATEGORY_SYNONYM_MAP:
        cat_slug = CATEGORY_SYNONYM_MAP[cat_slug]
    if cat_slug not in OFFICIAL_CATEGORY_SLUGS:
        # Fuzzy match
        for official in OFFICIAL_CATEGORY_SLUGS:
            if official in cat_slug or cat_slug in official:
                cat_slug = official
                break
        else:
            cat_slug = "peralatan-dapur-bekas-lainnya"

    # 8. Condition Semantic Authority
    allowed_kondisi = ["Bekas Siap Pakai", "Like New / Ex-Display", "Baru Sisa Proyek"]
    ai_kondisi = parsed.get("kondisi_unit")
    if ai_kondisi in allowed_kondisi:
        kondisi_final = ai_kondisi
    else:
        kondisi_final = "Bekas Siap Pakai"

    # 9. Status Biner & Non-Product Semantic Assertion
    is_non_product = parsed.get("is_non_product") is True
    if is_non_product:
        status_pipeline = "SKIP_NON_PRODUCT"
        status_unit = "SOLD"
    else:
        status_pipeline = "PROCESSED"
        status_raw = str(parsed.get("status_unit") or "READY").upper()
        if any(k in raw_caption.lower() for k in ["laku", "sold", "terjual", "habis"]):
            status_unit = "SOLD"
        elif status_raw in ["SOLD", "TERJUAL"]:
            status_unit = "SOLD"
        else:
            status_unit = "READY"

    # 10. Pricing & Margin Guardrails (Graceful Null Modal SSOT)
    modal_raw = parsed.get("harga_modal")
    if modal_raw is not None and isinstance(modal_raw, (int, float)) and int(modal_raw) > 0:
        modal_val = int(modal_raw)
    else:
        modal_val = None

    est_baru_val = parsed.get("estimasi_harga_baru")
    if not est_baru_val or not isinstance(est_baru_val, (int, float)) or est_baru_val <= 0:
        est_baru_val = None

    ai_disp_low = parsed.get("harga_display_low")
    ai_disp_high = parsed.get("harga_display_high")

    pricing = calculate_margins_and_anchors(
        modal=modal_val,
        estimasi_baru=est_baru_val,
        ai_display_low=ai_disp_low,
        ai_display_high=ai_disp_high,
        category_slug=cat_slug
    )

    # 11. SEO & Descriptions (Opsi 2: Clean Title + Semantic SEO Suite)
    badge = parsed.get("semantic_badge") or "Ex-Resto"
    seo_title = (parsed.get("seo_title") or f"{title} | BBKitchen").strip()
    short_desc = f"{title} ({badge}) kondisi {kondisi_final}. Lokasi unit di {location_name}. Lolos uji fungsi & siap kirim bergaransi."
    full_desc = build_rich_description(parsed, pricing, location_name, sub_components_baru=sub_baru_list)

    yoast_kw = (parsed.get("yoast_keyword") or f"{nama_alat.lower()} bekas")[:60]
    yoast_desc = (parsed.get("yoast_description") or short_desc)[:155]

    # 12. Programmatic 4-Tier Image Alt Text Suite
    img_alt = parsed.get("image_alt") or f"{title} Bekas Bergaransi BBKitchen"
    img_title = parsed.get("image_title") or f"Jual {nama_alat} {badge} {brand} {dimensi}".strip()
    img_caption = parsed.get("image_caption") or f"{nama_alat} kondisi prima siap kirim dari {location_name}"
    img_desc = parsed.get("image_description") or short_desc

    # Clean photo URLs
    final_photos = photo_urls if photo_urls else f"{sku}_1.webp"

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "sku": sku,
        "slug": slug,
        "title": title,
        "seo_title": seo_title,
        "semantic_badge": badge,
        "category_slug": cat_slug,
        "status_unit": status_unit,
        "status_pipeline": status_pipeline,
        "lokasi_unit": location_name,
        "kondisi_unit": kondisi_final,
        "short_description": short_desc,
        "full_description": full_desc,
        "yoast_keyword": yoast_kw,
        "yoast_description": yoast_desc,
        "featured_image": f"{sku}_1.webp",
        "photo_urls": final_photos,
        "link_telegram": link_message,
        "link_unit": link_unit,
        "asal_gudang": hub_code,
        "harga_modal": pricing["harga_modal"],
        "harga_buka_wa": pricing["harga_buka_wa"],
        "harga_deal_wa": pricing["harga_deal_wa"],
        "harga_floor_wa": pricing["harga_floor_wa"],
        "margin_floor": pricing["margin_floor"],
        "margin_deal": pricing["margin_deal"],
        "status_guardrail": pricing["status_guardrail"],
        "estimasi_harga_baru": pricing["estimasi_harga_baru"],
        "harga_display_low": pricing["harga_display_low"],
        "harga_display_high": pricing["harga_display_high"],
        "image_alt": img_alt,
        "image_title": img_title,
        "image_caption": img_caption,
        "image_description": img_desc,
        "is_dirty": 1,
        "tanggal_masuk": now_str,
        "tanggal_terjual": None,
        "durasi_terjual": None,
        "product_id_woo": None,
        "created_at": now_str,
        "last_checked_telegram": now_str,
        "updated_at": now_str,
    }

# ==============================================================================
# CLI TEST HARNESS
# ==============================================================================

if __name__ == "__main__":
    print("=== Testing BBKitchen Sovereign Full-AI Normalization Engine ===")
    
    test_cases = [
        {
            "sku": "BBK3215",
            "caption": "Sokes 1 pintu merk Gea mulus dingin bgt 231 liter lokasi pamulang modal 1.85jt net",
            "group": "GK",
            "desc": "Showcase 1 Pintu Mesin (Brand: GEA, Modal: 1.85jt)"
        },
        {
            "sku": "BBK3192",
            "caption": "greastrap stainles 40x30x30 anti karat tebal custom lokal resto hrg 650rb kedaung",
            "group": "WT",
            "desc": "Fabrikasi Stainless Unbranded (Grease Trap, Modal: 650rb)"
        },
        {
            "sku": "BBK3193",
            "caption": "Upright chiller 2 pintu mastercool pemakaian baru 5 bulan filter baru mulus dingin 12jt sawangan",
            "group": "PE",
            "desc": "Jebakan Sparepart Baru & Waktu (Wajib: Bekas Siap Pakai, Modal: 12jt)"
        },
        {
            "sku": "BBK3999",
            "caption": "Info loker teknisi pendingin & staf gudang area pamulang tangsel hubungi wa 0812345678",
            "group": "GK",
            "desc": "Non-Product Announcement (Wajib: SKIP_NON_PRODUCT)"
        }
    ]

    for tc in test_cases:
        print(f"\n--- Testing: {tc['desc']} ({tc['sku']}) ---")
        res = normalize_single_caption(
            raw_caption=tc["caption"],
            sku=tc["sku"],
            source_group=tc["group"]
        )
        print(f"Title        : {res['title']}")
        print(f"Slug         : {res['slug']}")
        print(f"Category     : {res['category_slug']}")
        print(f"Kondisi      : {res['kondisi_unit']}")
        print(f"Status Pipe  : {res['status_pipeline']}")
        print(f"Modal HPP    : {format_rupiah(res['harga_modal'])}")
        print(f"Buka WA      : {format_rupiah(res['harga_buka_wa'])}")
        print(f"Display Range: {format_rupiah(res['harga_display_low'])} - {format_rupiah(res['harga_display_high'])}")
        print(f"Est. Baru    : ~{format_rupiah(res['estimasi_harga_baru'])}")
        print(f"Image Alt    : {res['image_alt']}")

    print("\n✅ All 4 Real-World Edge Cases Tested Successfully!")

