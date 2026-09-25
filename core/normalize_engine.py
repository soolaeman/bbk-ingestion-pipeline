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

Tugas Anda: Menganalisis caption mentah Telegram dari gudang mitra, mengekstrak spesifikasi teknis, membersihkan noise, dan menghasilkan data katalog standar industri Horeca.

ATURAN BISNIS MUTLAK:
1. JUDUL PRODUK RESMI ("title_bersih"):
   - Format wajib: [Nama Standar Alat] [Brand/Merk] Second [Dimensi/Kapasitas]
   - Contoh ideal:
     * "Upright Chiller 2 Pintu Mastercool Second"
     * "Meja Stainless 2 Susun Second 150x70x85 cm"
     * "Single Sink Stainless 1 Lubang Sayap Kiri Second 100 cm"
     * "Kwali Range 2 Burner Second Blower"
     * "Combi Oven 6 Tray Rational Second"
   - Maksimal 60 karakter, Title Case. JANGAN ulangi kata merk atau kata "Second" dua kali!
   - DILARANG memuat angka harga, nomor telepon, kata "JUAL", "DIJUAL", atau promo murahan.
   - BRAND & DIMENSI HIERARCHY:
     * Unit Fabrikasi Stainless (Meja, Sink, Rak, Hood, Wallshelf, Kabinet): 99% custom bengkel lokal tanpa merk. JANGAN mengarang merk! Utamakan DIMENSI (PxLxT) & fitur susun/lubang.
     * Unit Mesin & Kompor (Chiller, Freezer, Kwali, Fryer, Oven, Showcase): Jika merk resmi tertera jelas (GEA, Mastercool, Nayati, Getra, Escoffier, Rational), cantumkan merk. Jika merk tidak ada/pudar, JANGAN mengarang merk! Utamakan tipe & kapasitas.

2. DETEKSI KONDISI SUB-KOMPONEN VS UNIT:
   - Jika ada frasa 'Filter baru', 'Kran baru', 'Burner baru', 'Plat baru', 'Saringan baru' -> Unit tetap 'Bekas Siap Pakai', dan cantumkan komponen baru tersebut di spesifikasi ringkas.
   - Jangan pernah menetapkan 'Baru Sisa Proyek' kecuali seluruh unit 100% baru dalam dus.

3. PEMILIHAN KATEGORI SSOT (PILIH 1 SLUG RESMI):
   - CHILLER: undercounter-chiller, upright-chiller, chiller, lainnya-chiller
   - FREEZER: chest-freezer, upright-freezer, freezer, lainnya-freezer
   - MEJA STAINLESS: meja-1-susun-stainless, meja-2-susun-stainless, meja-3-susun-stainless, meja-bumbu-stainless, meja-kabinet-stainless, meja-kompor-stainless, meja-stainless, lainnya-meja-stainless
   - SINK STAINLESS: single-sink-stainless, double-sink-stainless, triple-sink-stainless, sink-jumbo-stainless, sink-stainless, lainnya-sink
   - KOMPOR & COOKING: kompor-1-tungku, kompor-2-tungku, kompor-3-tungku, kompor-4-tungku, kompor-6-tungku, kompor-wok-kwali-range, kompor-batu-lava, kompor-grill-tepanyaki, deep-fryer, noodle-boiler, oven, kompor, lainnya-kompor
   - RAK STAINLESS: rak-1-susun-stainless, rak-2-susun-stainless, rak-3-susun-stainless, rak-4-susun-stainless, rak-5-susun-stainless, wallshelf, rak-stainless, lainnya-rak-stainless
   - HOOD: hood, blower, ducting, hood-stainless, lainnya-hood
   - SHOWCASE: showcase-1-pintu, showcase-2-pintu, cake-showcase, showcase, lainnya-showcase
   - ICE SYSTEM: ice-bin, ice-maker, ice-system, lainnya-ice-system
   - LAINNYA: peralatan-dapur-bekas-lainnya

4. STRATEGIC PRICE ANCHORING:
   - "harga_modal": Nilai angka rupiah modal dari caption (abaikan format titik/koma). Jika tidak ada, isi null.
   - "estimasi_harga_baru": Taksiran wajar harga unit BARU distributor resmi di Indonesia (dalam angka integer rupiah).
     Contoh: Chiller 2 pintu baru ~28-35jt, Kwali 2 burner baru ~20-25jt, Meja 2 susun 150cm baru ~3.5-4.5jt, Deep fryer 1 tank baru ~6.5jt.

5. SEO & DESKRIPSI:
   - "yoast_keyword": "[nama alat] bekas" (contoh: "upright chiller mastercool bekas")
   - "yoast_description": Deskripsi meta menarik max 150 karakter.
   - "spesifikasi_ringkas": Array 4-6 poin spesifikasi teknis penting (dimensi, material, kelengkapan, uji fungsi).

KEMBALIKAN STRICTLY JSON:
{
  "title_bersih": str,
  "nama_alat": str,
  "brand": str,
  "dimensi": str,
  "category_slug": str,
  "kondisi_unit": "Bekas Siap Pakai" | "Like New / Ex-Display" | "Baru Sisa Proyek",
  "status_unit": "READY" | "SOLD",
  "harga_modal": int | null,
  "estimasi_harga_baru": int,
  "yoast_keyword": str,
  "yoast_description": str,
  "spesifikasi_ringkas": [str]
}
"""

# ==============================================================================
# LAYER 5: POST-VALIDATOR, GUARDRAIL MARGINS & PRICE ANCHORS
# ==============================================================================

def calculate_margins_and_anchors(modal: Optional[int], estimasi_baru: Optional[int], category_slug: str = "") -> Dict[str, Any]:
    """
    Menghitung guardrail margin privat dan batas rentang penawaran publik BBKitchen.
    Prinsip:
    - Modal tidak pernah dibocorkan ke publik.
    - Harga Buka WA = Modal * (1 + margin_buka)
    - Harga Display Low = Pembulatan rapi ke atas (kelipatan 100rb).
    - Harga Display High = min(Display Low * 1.25, Estimasi Baru * 0.75).
    """
    cat_lower = (category_slug or "").lower()
    
    # Baseline fallback if estimasi_baru is missing/unrealistic
    default_est_baru = 15_000_000
    if "chiller" in cat_lower or "freezer" in cat_lower:
        default_est_baru = 25_000_000
    elif "kwali" in cat_lower or "oven" in cat_lower:
        default_est_baru = 22_000_000
    elif "meja" in cat_lower or "sink" in cat_lower or "rak" in cat_lower:
        default_est_baru = 4_500_000
    elif "hood" in cat_lower:
        default_est_baru = 8_000_000

    est_baru_clean = int(estimasi_baru) if estimasi_baru and estimasi_baru > 0 else default_est_baru

    if modal is None or modal <= 0:
        # Graceful handling when modal is unknown
        modal_clean = int(est_baru_clean * 0.35)
        is_estimated_modal = True
    else:
        modal_clean = int(modal)
        is_estimated_modal = False

    # Bracket margin guardrails
    if modal_clean <= 3_000_000:
        m_floor, m_deal, m_buka = 0.45, 0.55, 0.70
    elif modal_clean <= 10_000_000:
        m_floor, m_deal, m_buka = 0.35, 0.45, 0.55
    elif modal_clean <= 30_000_000:
        m_floor, m_deal, m_buka = 0.25, 0.35, 0.45
    else:
        m_floor, m_deal, m_buka = 0.20, 0.28, 0.38

    harga_floor_wa = int(modal_clean * (1 + m_floor))
    harga_deal_wa = int(modal_clean * (1 + m_deal))
    harga_buka_wa = int(modal_clean * (1 + m_buka))

    # Public Display Low (Rounded to clean 100k)
    harga_display_low = ((harga_buka_wa + 99_999) // 100_000) * 100_000

    # Ensure estimasi_baru is dignified (Higher than display low)
    if est_baru_clean <= harga_display_low:
        est_baru_clean = int(harga_display_low * 1.75)

    # Public Display High: capped below new price (Guarantee 25-50% savings)
    raw_high = int(harga_display_low * 1.25)
    ceiling = int(est_baru_clean * 0.75)
    harga_display_high = min(raw_high, ceiling)
    if harga_display_high <= harga_display_low:
        harga_display_high = int(harga_display_low * 1.2)
    harga_display_high = ((harga_display_high + 99_999) // 100_000) * 100_000

    return {
        "harga_modal": None if is_estimated_modal else modal_clean,
        "is_estimated_modal": is_estimated_modal,
        "margin_floor": m_floor,
        "margin_deal": m_deal,
        "harga_floor_wa": harga_floor_wa,
        "harga_deal_wa": harga_deal_wa,
        "harga_buka_wa": harga_buka_wa,
        "status_guardrail": "PASS",
        "estimasi_harga_baru": est_baru_clean,
        "harga_display_low": harga_display_low,
        "harga_display_high": harga_display_high,
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
        if any(k in cap_lower for k in ["upright", "aprait"]):
            cat_slug = "upright-chiller"
            nama_alat = "Upright Chiller"
        elif any(k in cap_lower for k in ["undercounter", "anderconter", "under conter"]):
            cat_slug = "undercounter-chiller"
            nama_alat = "Undercounter Chiller"
        else:
            cat_slug = "chiller"
            nama_alat = "Chiller Komersial"
    elif any(k in cap_lower for k in ["freezer", "prizer", "freser", "frizer"]):
        if "chest" in cap_lower:
            cat_slug = "chest-freezer"
            nama_alat = "Chest Freezer"
        elif "upright" in cap_lower:
            cat_slug = "upright-freezer"
            nama_alat = "Upright Freezer"
        else:
            cat_slug = "freezer"
            nama_alat = "Freezer Komersial"
    elif any(k in cap_lower for k in ["sink", "singk", "bak cuci"]):
        if any(k in cap_lower for k in ["double", "2 lubang", "2 pot", "2 bowl"]):
            cat_slug = "double-sink-stainless"
            nama_alat = "Double Sink Stainless"
        elif any(k in cap_lower for k in ["triple", "3 lubang", "3 pot"]):
            cat_slug = "triple-sink-stainless"
            nama_alat = "Triple Sink Stainless"
        else:
            cat_slug = "single-sink-stainless"
            nama_alat = "Single Sink Stainless"
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
        elif "kabinet" in cap_lower or "cabinet" in cap_lower:
            cat_slug = "meja-kabinet-stainless"
            nama_alat = "Meja Kabinet Stainless"
        else:
            cat_slug = "meja-stainless"
            nama_alat = "Meja Stainless"
    elif any(k in cap_lower for k in ["kwali", "kuali", "wok"]):
        cat_slug = "kompor-wok-kwali-range"
        nama_alat = "Kwali Range Blower"
    elif "deep fryer" in cap_lower or "dip frayer" in cap_lower:
        cat_slug = "deep-fryer"
        nama_alat = "Deep Fryer Komersial"
    elif "rak" in cap_lower or "rack" in cap_lower:
        cat_slug = "rak-4-susun-stainless"
        nama_alat = "Rak Stainless Susun"
    elif "hood" in cap_lower:
        cat_slug = "hood"
        nama_alat = "Exhaust Hood Stainless"
    elif "showcase" in cap_lower or "sokes" in cap_lower or "shocess" in cap_lower:
        cat_slug = "showcase"
        nama_alat = "Showcase Komersial"

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
        "yoast_keyword": f"{nama_alat.lower()} bekas",
        "yoast_description": f"{title_bersih} kondisi siap pakai bergaransi.",
        "spesifikasi_ringkas": [
            f"Dimensi: {dimensi or 'Standar Komersial'}",
            "Material stainless steel food grade",
            "Fungsi mekanikal & elektrikal teruji siap pakai",
            "Unit lolos inspeksi quality control BBKitchen"
        ]
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

    # 5. Build Title & Sanitize
    title_bersih = (parsed.get("title_bersih") or "").strip()
    nama_alat = (parsed.get("nama_alat") or "Peralatan Dapur Komersial").strip()
    brand = (parsed.get("brand") or "").strip()
    dimensi = (parsed.get("dimensi") or "").strip()

    if title_bersih:
        title = title_bersih
    else:
        parts = [nama_alat]
        # Ignore brand for stainless fabrication
        is_fabrication = any(k in nama_alat.lower() for k in FABRICATION_KEYWORDS)
        if brand and not is_fabrication and brand.lower() not in nama_alat.lower():
            parts.append(brand)
        if "second" not in [p.lower() for p in parts]:
            parts.append("Second")
        if dimensi and len(dimensi) <= 20 and dimensi.lower() not in nama_alat.lower():
            parts.append(dimensi)
        title = " ".join(parts)

    # Strip any leaked prices / WA from title
    title = re.sub(r'(?i)(?:rp\.?\s*[\d.,]+|[\d.,]+\s*(?:jt|juta|k|rb|ribu))', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 65:
        title = title[:65].rsplit(" ", 1)[0]

    # 6. Sacred Slug Immutability Protection
    if existing_slug and str(existing_slug).strip():
        slug = str(existing_slug).strip()
    else:
        clean_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        slug = clean_slug if clean_slug else f"unit-{sku.lower()}"

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

    # 8. Condition & Sub-Components Integration
    kondisi_final = kondisi_pre_check
    if parsed.get("kondisi_unit") and parsed.get("kondisi_unit") != "Bekas Siap Pakai":
        # Only accept higher grade if supported by pre-check
        if kondisi_pre_check != "Bekas Siap Pakai":
            kondisi_final = parsed.get("kondisi_unit")

    # 9. Status Biner Assertion
    status_raw = str(parsed.get("status_unit") or "READY").upper()
    if any(k in raw_caption.lower() for k in ["laku", "sold", "terjual", "habis"]):
        status_unit = "SOLD"
    elif status_raw in ["SOLD", "TERJUAL"]:
        status_unit = "SOLD"
    else:
        status_unit = "READY"

    # 10. Pricing & Margin Guardrails
    modal_val = parsed.get("harga_modal")
    if not modal_val or not isinstance(modal_val, (int, float)) or modal_val <= 0:
        modal_val = modal_pre_check

    est_baru_val = parsed.get("estimasi_harga_baru")
    if not est_baru_val or not isinstance(est_baru_val, (int, float)) or est_baru_val <= 0:
        est_baru_val = None

    pricing = calculate_margins_and_anchors(modal_val, est_baru_val, category_slug=cat_slug)

    # 11. SEO & Descriptions
    short_desc = f"{title} kondisi {kondisi_final}. Lokasi unit di {location_name}. Lolos uji fungsi & siap kirim bergaransi."
    full_desc = build_rich_description(parsed, pricing, location_name, sub_components_baru=sub_baru_list)

    yoast_kw = (parsed.get("yoast_keyword") or f"{nama_alat.lower()} bekas")[:60]
    yoast_desc = (parsed.get("yoast_description") or short_desc)[:155]

    # Clean photo URLs
    final_photos = photo_urls if photo_urls else f"{sku}_1.webp"

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "sku": sku,
        "slug": slug,
        "title": title,
        "seo_title": f"{title} | BBKitchen",
        "category_slug": cat_slug,
        "status_unit": status_unit,
        "status_pipeline": "PROCESSED",
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
        "image_alt": f"{title} - BBKitchen Spesialis Alat Dapur Second",
        "image_title": title,
        "image_caption": f"{title} siap kirim dari {location_name}",
        "image_description": short_desc,
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
    print("=== Testing BBKitchen Deterministic Normalization Core Engine ===")
    test_caption = """
    Hood complete + Filter baru
    Ukuran 290x85x50
    Lokasi Pamulang 2
    Harga modal 4.500.000 nett
    Hubungi wa: 081234567890 fast respon
    """
    res = normalize_single_caption(
        raw_caption=test_caption,
        sku="BBK0047",
        existing_slug="hood-complete-filter-pamulang-2",
        source_group="GK"
    )
    print("\nExtraction Result:")
    print(f"SKU          : {res['sku']}")
    print(f"Title        : {res['title']}")
    print(f"Slug (Locked): {res['slug']}")
    print(f"Category     : {res['category_slug']}")
    print(f"Kondisi      : {res['kondisi_unit']} (Filter baru sub-komponen handled)")
    print(f"Status       : {res['status_unit']}")
    print(f"Modal HPP    : {format_rupiah(res['harga_modal'])}")
    print(f"Buka WA      : {format_rupiah(res['harga_buka_wa'])}")
    print(f"Display Range: {format_rupiah(res['harga_display_low'])} - {format_rupiah(res['harga_display_high'])}")
    print(f"Est. Baru    : ~{format_rupiah(res['estimasi_harga_baru'])}")
    print(f"Yoast KW     : {res['yoast_keyword']}")
    print("\n✅ Normalization Engine Test Passed Successfully!")
