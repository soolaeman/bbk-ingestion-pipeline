# -*- coding: utf-8 -*-
"""
👑 BBKitchen Pure Regex MVP Batch Normalizer & Anomaly Auditor
Analyzes all 3,147 raw records in bbk.db purely via deterministic regex (0 AI tokens, 0 network lag),
identifies ambiguous edge cases, and produces a structured review report for human verification.
"""

import os
import re
import sys
import json
import sqlite3
from typing import Dict, Any, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "..", "core")
for p in [BASE_DIR, CORE_DIR]:
    if p not in sys.path:
        sys.path.append(p)

from normalize_engine import (
    sanitize_raw_caption,
    extract_modal_regex,
    evaluate_condition_binary,
    resolve_warehouse_partner,
    calculate_margins_and_anchors,
    format_rupiah,
    KNOWN_COMMERCIAL_BRANDS,
    FABRICATION_KEYWORDS,
    OFFICIAL_CATEGORY_SLUGS,
    CATEGORY_SYNONYM_MAP,
)

DB_PATH = os.path.join(BASE_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db")
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, "..", "bbk.db")

REPORT_PATH = os.path.join(BASE_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "docs", "notes", "REGEX_MVP_AUDIT_REVIEW.md")

# ==============================================================================
# ENHANCED DETERMINISTIC REGEX PARSER (PURE MVP)
# ==============================================================================

def parse_regex_mvp(caption: str, sku: str, existing_slug: str = None, source_group: str = "", link_msg: str = "") -> Dict[str, Any]:
    """Pure deterministic regex extraction without LLM."""
    sanitized = sanitize_raw_caption(caption)
    cap_lower = sanitized.lower()

    # 1. Non-product filter
    is_non_product = bool(re.search(r'\b(info\s*penipu|jnt\s*cargo|j&t|terima\s*pembuatan\s*meja|harga\s*baru\s*nya\s*dgn\s*model|ready\s*mesin\s*fotocopy|sedot\s*wc|loker|lowongan|kolektor\s*item|patung|karya\s*:\s*ary|tv\s*\d+\s*inch|cermin\s*dinding|assalamualaikum\s*tmn2\s*marketing)\b', cap_lower))

    # 2. Extract dimensions (PxLxT or P 100 x L 70 x T 80 or 100x70x80 or P.112 L 46 T 180 or P150cm L 70 T 85)
    dimensi = ""
    # Case A: Explicit P x L x T format with optional dots, cm, and spaces
    plt_match = re.search(r'\bP\.?\s*(\d{2,3}(?:\.\d+)?)\s*(?:cm)?\s*(?:x|,|\s+)\s*L\.?\s*(\d{2,3}(?:\.\d+)?)\s*(?:cm)?(?:\s*(?:x|,|\s+)\s*T\.?\s*(\d{2,3}(?:\.\d+)?)\s*(?:cm)?)?\b', sanitized, re.IGNORECASE)
    if plt_match:
        p, l, t = plt_match.group(1), plt_match.group(2), plt_match.group(3)
        p = p.replace(".0", "")
        l = l.replace(".0", "")
        if t:
            t = t.replace(".0", "")
            dimensi = f"{p}x{l}x{t}"
        else:
            dimensi = f"{p}x{l}"
    
    # Case B: Standard 120x60x85 or 120 x 60 x 85 cm
    if not dimensi:
        std_match = re.search(r'(\d{2,3}(?:\.\d+)?\s*[xX*×]\s*\d{2,3}(?:\.\d+)?(?:\s*[xX*×]\s*\d{2,3}(?:\.\d+)?)?(?:\s*cm|\s*m|\s*mm)?)', sanitized)
        if std_match:
            raw_dim = std_match.group(1).replace("×", "x").replace("*", "x").replace(" ", "").replace("cm", "").replace("mm", "")
            raw_dim = re.sub(r'^(?:uk|ukuran|dimensi)[:.\-]?\s*', '', raw_dim, flags=re.IGNORECASE)
            if len(raw_dim) <= 20 and 'x' in raw_dim:
                dimensi = raw_dim

    # Case C: Prefix uk / ukuran / dimensi
    if not dimensi:
        uk_match = re.search(r'\b(?:uk|ukuran|dimensi)\.?\s*[:.\-]?\s*P?\.?\s*(\d{2,3})\s*(?:cm)?\s*[xX*×\s]\s*L?\.?\s*(\d{2,3})(?:\s*(?:cm)?\s*[xX*×\s]\s*T?\.?\s*(\d{2,3}))?\b', sanitized, re.IGNORECASE)
        if uk_match:
            p, l, t = uk_match.group(1), uk_match.group(2), uk_match.group(3)
            dimensi = f"{p}x{l}x{t}" if t else f"{p}x{l}"

    # Case D: Diameter
    if not dimensi:
        dia_match = re.search(r'\b(?:diameter|d)\s*[:.\-]?\s*(\d{2,3})\s*(?:cm)?(?:\s*tinggi\s*(\d{2,3}))?\b', sanitized, re.IGNORECASE)
        if dia_match:
            d_val = dia_match.group(1)
            t_val = dia_match.group(2)
            dimensi = f"D{d_val}xT{t_val}" if t_val else f"D{d_val}"

    # 3. Detect Brand
    brand = ""
    for b in KNOWN_COMMERCIAL_BRANDS:
        if re.search(rf'\b{re.escape(b)}\b', sanitized, re.IGNORECASE):
            brand = b
            break

    # 4. Deterministic Category & Equipment Classifier (58 SSOT)
    cat_slug = "peralatan-dapur-bekas-lainnya"
    nama_alat = "Peralatan Dapur Komersial"
    confidence = "HIGH"
    uncertainty_reason = ""

    # Rule 1: Chiller & Freezer
    if any(k in cap_lower for k in ["cake showcase", "showcase cake"]):
        cat_slug = "cake-showcase"
        nama_alat = "Cake Showcase"
    elif any(k in cap_lower for k in ["sushi showcase"]):
        cat_slug = "showcase-1-pintu"
        nama_alat = "Sushi Showcase"
    elif any(k in cap_lower for k in ["showcase 2 pintu", "showcase 3 pintu", "open chiller", "multideck", "multidek"]):
        cat_slug = "showcase-2-pintu"
        nama_alat = "Showcase 2 Pintu"
    elif any(k in cap_lower for k in ["showcase", "sokes", "shocess", "chocase", "shoches"]):
        cat_slug = "showcase-1-pintu"
        nama_alat = "Showcase 1 Pintu"
    elif any(k in cap_lower for k in ["undercounter freezer", "under counter freezer", "under conter freezer", "ucf"]):
        cat_slug = "freezer"
        nama_alat = "Undercounter Freezer"
    elif any(k in cap_lower for k in ["undercounter", "under counter", "anderconter", "ucc", "counter top salad", "salad pan", "salad bar"]):
        cat_slug = "undercounter-chiller"
        nama_alat = "Undercounter Chiller"
    elif any(k in cap_lower for k in ["chest freezer", "freezer box", "frezer box", "sliding freezer", "freser box"]):
        cat_slug = "chest-freezer"
        nama_alat = "Chest Freezer"
    elif any(k in cap_lower for k in ["upright freezer", "uprig frizer", "freezer 2 pintu", "freezer 4 pintu", "freezer 6 pintu"]):
        cat_slug = "upright-freezer"
        nama_alat = "Upright Freezer"
    elif any(k in cap_lower for k in ["upright chiller", "uprig chiller", "aprait ciler", "chiller 2 pintu", "chiller 4 pintu", "chiller 6 pintu", "chiller 1 pintu"]):
        cat_slug = "upright-chiller"
        nama_alat = "Upright Chiller"
    elif any(k in cap_lower for k in ["freezer", "prizer", "freser", "frizer"]):
        cat_slug = "freezer"
        nama_alat = "Freezer Komersial"
    elif any(k in cap_lower for k in ["chiller", "ciler", "ciller"]):
        cat_slug = "chiller"
        nama_alat = "Chiller Komersial"

    # Rule 2: Ice System
    elif any(k in cap_lower for k in ["ice maker", "icemeker", "mesin es", "es serut", "ice serut", "ice crusher", "pembuat es"]):
        cat_slug = "ice-maker"
        nama_alat = "Ice Maker"
    elif any(k in cap_lower for k in ["ice bin", "icebin", "ice bean", "ice box stainless", "bin es"]):
        cat_slug = "ice-bin"
        nama_alat = "Ice Bin Stainless"

    # Rule 3: Cooking & Cooking Equipment
    elif any(k in cap_lower for k in ["deep fryer", "deepfryer", "deepfrayer", "defreyer", "dip frayer", "dipfrayer", "difleyer", "deepfreyer", "preyer gas", "fryer gas", "fryer listrik", "electric fryer"]):
        cat_slug = "deep-fryer"
        nama_alat = "Deep Fryer"
    elif any(k in cap_lower for k in ["noodle boiler", "noodle", "rebus mie", "boiler mie"]):
        cat_slug = "noodle-boiler"
        nama_alat = "Noodle Boiler"
    elif any(k in cap_lower for k in ["batu lava", "lava rock", "lava stone"]):
        cat_slug = "kompor-batu-lava"
        nama_alat = "Kompor Batu Lava"
    elif any(k in cap_lower for k in ["tepan", "teppan", "teppanyaki", "griddle", "salamander", "charbroiler", "flat griddle", "grooved griddle", "roller grill"]):
        cat_slug = "kompor-grill-tepanyaki"
        nama_alat = "Kompor Grill Teppanyaki"
    elif re.search(r'\b(combi\s*oven|convection\s*oven|deck\s*oven|pizza\s*oven|rotisserie|oven)\b', cap_lower):
        cat_slug = "oven"
        nama_alat = "Oven Komersial"
    elif any(k in cap_lower for k in ["kwali", "kuali", "wok range", "kwali blower", "kuali ren", "kwalirange"]):
        cat_slug = "kompor-wok-kwali-range"
        nama_alat = "Kwali Range Blower"
    elif any(k in cap_lower for k in ["steamer dimsum", "rice steamer", "kukusan dimsum", "dimsum steamer", "mesin kukus", "staimer dimsam"]):
        cat_slug = "lainnya-kompor"
        nama_alat = "Dimsum Steamer"
    elif any(k in cap_lower for k in ["rice cooker", "gas rice cooker", "pemasak nasi", "penanak nasi"]):
        cat_slug = "lainnya-kompor"
        nama_alat = "Commercial Gas Rice Cooker"
    elif any(k in cap_lower for k in ["bain marie", "bainmarie", "pemanas sayur", "food warmer", "warmer display", "etalase pemanas", "warmer"]):
        cat_slug = "lainnya-kompor"
        nama_alat = "Bain Marie Stainless"
    elif any(k in cap_lower for k in ["water boiler", "pemanas air", "water dispenser komersial"]):
        cat_slug = "lainnya-kompor"
        nama_alat = "Water Boiler Commercial"
    elif re.search(r'\b(?:6|enam)\s*(?:tungku|burner)\b|stove\s*6', cap_lower):
        cat_slug = "kompor-6-tungku"
        nama_alat = "Kompor 6 Tungku"
    elif re.search(r'\b(?:4|empat)\s*(?:tungku|burner)\b|stove\s*4', cap_lower):
        cat_slug = "kompor-4-tungku"
        nama_alat = "Kompor 4 Tungku"
    elif re.search(r'\b(?:3|tiga)\s*(?:tungku|burner)\b|stove\s*3', cap_lower):
        cat_slug = "kompor-3-tungku"
        nama_alat = "Kompor 3 Tungku"
    elif re.search(r'\b(?:2|dua)\s*(?:tungku|burner)\b|stove\s*2', cap_lower):
        cat_slug = "kompor-2-tungku"
        nama_alat = "Kompor 2 Tungku"
    elif re.search(r'\b(?:1|satu)\s*(?:tungku|burner)\b|stove\s*1|stockpot|stokpot', cap_lower):
        cat_slug = "kompor-1-tungku"
        nama_alat = "Kompor 1 Tungku"
    elif re.search(r'\b(kompor|stove|gas range|high pressure|low pressure)\b', cap_lower):
        cat_slug = "kompor"
        nama_alat = "Kompor Komersial"

    # Rule 4: Ventilasi
    elif re.search(r'\b(cooker\s*hood|exhaust\s*hood|hood)\b', cap_lower):
        cat_slug = "hood"
        nama_alat = "Exhaust Hood Stainless"
    elif any(k in cap_lower for k in ["blower", "axial fan", "exhaust fan", "sirocco"]):
        cat_slug = "blower"
        nama_alat = "Blower Exhaust"
    elif re.search(r'\bducting\b', cap_lower):
        cat_slug = "ducting"
        nama_alat = "Ducting Stainless"

    # Rule 5: Sink & Grease Trap
    elif any(k in cap_lower for k in ["grease trap", "greasetrap", "greastrep", "gris trap", "perangkap lemak", "jebakan lemak"]):
        cat_slug = "lainnya-sink"
        nama_alat = "Grease Trap Stainless"
    elif any(k in cap_lower for k in ["gutter", "guiter", "gutter grill", "tutup selokan", "drainage gutter"]):
        cat_slug = "lainnya-sink"
        nama_alat = "Gutter Stainless Grill"
    elif any(k in cap_lower for k in ["sink jumbo", "bak jumbo"]):
        cat_slug = "sink-jumbo-stainless"
        nama_alat = "Single Sink Jumbo Stainless"
    elif re.search(r'\b(triple\s*sink|3\s*l[ou]bang|3\s*bowl|3\s*pot|3\s*hole|tiga\s*l[ou]bang)\b', cap_lower) or any(k in cap_lower for k in ["lobang ke2 sama ke 3", "3 lubang", "3 lobang"]):
        cat_slug = "triple-sink-stainless"
        nama_alat = "Triple Sink Stainless 3 Lubang"
    elif re.search(r'\b(double\s*sink|dobel\s*sink|2\s*l[ou]bang|2\s*bowl|2\s*pot|2\s*hole|dua\s*l[ou]bang)\b', cap_lower):
        cat_slug = "double-sink-stainless"
        nama_alat = "Double Sink Stainless 2 Lubang"
    elif re.search(r'\b(sink|singk|bak\s*cuci|wastafel|cuci\s*ikan|cuci\s*piring)\b', cap_lower):
        cat_slug = "single-sink-stainless"
        nama_alat = "Single Sink Stainless 1 Lubang"

    # Rule 6: Rak & Wallshelf
    elif any(k in cap_lower for k in ["wallshelf", "wall shelf", "wall selp", "rak dinding", "rak gantung", "upper shelf", "ambalan gantung"]):
        cat_slug = "wallshelf"
        nama_alat = "Wallshelf Stainless"
    elif re.search(r'\b(?:rak|tirisan).*(?:5|6|lima|enam)\s*(?:susun|trap|tier|tingkat|ambalan)\b', cap_lower):
        cat_slug = "rak-5-susun-stainless"
        nama_alat = "Rak Stainless 5 Susun"
    elif re.search(r'\b(?:rak|tirisan).*(?:4|empat)\s*(?:susun|trap|tier|tingkat|ambalan)\b', cap_lower) or any(k in cap_lower for k in ["rak 4 susun", "rak 4 trap", "tirisan 4 susun"]):
        cat_slug = "rak-4-susun-stainless"
        nama_alat = "Rak Stainless 4 Susun"
    elif re.search(r'\b(?:rak|tirisan).*(?:3|tiga)\s*(?:susun|trap|tier|tingkat|ambalan)\b', cap_lower) or any(k in cap_lower for k in ["rak 3 susun", "rak 3 trap"]):
        cat_slug = "rak-3-susun-stainless"
        nama_alat = "Rak Stainless 3 Susun"
    elif re.search(r'\b(?:rak|tirisan).*(?:2|dua)\s*(?:susun|trap|tier|tingkat|ambalan)\b', cap_lower) or any(k in cap_lower for k in ["rak 2 susun", "rak 2 trap"]):
        cat_slug = "rak-2-susun-stainless"
        nama_alat = "Rak Stainless 2 Susun"
    elif re.search(r'\b(?:rak|tirisan).*(?:1|satu)\s*(?:susun|trap|tier|tingkat|ambalan)\b', cap_lower):
        cat_slug = "rak-1-susun-stainless"
        nama_alat = "Rak Stainless 1 Susun"
    elif re.search(r'\b(rak|rack|tirisan)\b', cap_lower):
        cat_slug = "rak-stainless"
        nama_alat = "Rak Stainless"

    # Rule 7: Meja Stainless & Kabinet
    elif any(k in cap_lower for k in ["meja kompor", "meja dandang"]):
        cat_slug = "meja-kompor-stainless"
        nama_alat = "Meja Kompor Stainless"
    elif any(k in cap_lower for k in ["meja bumbu"]):
        cat_slug = "meja-bumbu-stainless"
        nama_alat = "Meja Bumbu Stainless"
    elif any(k in cap_lower for k in ["kabinet", "cabinet", "pintu sliding", "pintu swing", "meja kabinet", "cupboard"]):
        cat_slug = "meja-kabinet-stainless"
        nama_alat = "Meja Kabinet Stainless"
    elif re.search(r'\bmeja.*(?:3|tiga)\s*(?:susun|trap|tier|tingkat|ambalan)\b', cap_lower) or any(k in cap_lower for k in ["meja 3 susun", "meja 3 trap"]):
        cat_slug = "meja-3-susun-stainless"
        nama_alat = "Meja Stainless 3 Susun"
    elif re.search(r'\bmeja.*(?:2|dua)\s*(?:susun|trap|tier|tingkat|ambalan)\b', cap_lower) or any(k in cap_lower for k in ["meja 2 susun", "meja 2 trap", "meja prepare", "meja kerja", "meja priper"]):
        cat_slug = "meja-2-susun-stainless"
        nama_alat = "Meja Stainless 2 Susun"
    elif re.search(r'\bmeja.*(?:1|satu)\s*(?:susun|trap|tier|tingkat|ambalan)\b', cap_lower) or any(k in cap_lower for k in ["meja 1 susun", "meja 1 trap"]):
        cat_slug = "meja-1-susun-stainless"
        nama_alat = "Meja Stainless 1 Susun"
    elif re.search(r'\bmeja\b', cap_lower):
        cat_slug = "meja-stainless"
        nama_alat = "Meja Stainless"

    # Rule 8: Food Processing & Bakery Machinery (Peralatan Dapur Bekas Lainnya)
    elif any(k in cap_lower for k in ["juice dispenser", "jus dispenser", "dispenser jus", "dispenser juice"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Juice Dispenser Komersial"
    elif any(k in cap_lower for k in ["fruktosa", "penakar gula", "fructose dispenser"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Mesin Penakar Gula Fruktosa"
    elif any(k in cap_lower for k in ["air curtain", "tirai udara"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Air Curtain Komersial"
    elif any(k in cap_lower for k in ["chafing dish", "pemanas prasmanan"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Chafing Dish Prasmanan"
    elif any(k in cap_lower for k in ["parut kelapa"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Mesin Parut Kelapa Komersial"
    elif any(k in cap_lower for k in ["troli", "troly", "trolley"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Troli Stainless Bakery" if any(k in cap_lower for k in ["tray", "loyang", "bakery", "roti"]) else "Troli Makanan Stainless"
    elif any(k in cap_lower for k in ["planetari mixer", "planetary mixer", "spiral mixer", "mixer adonan", "stand mixer", "meat mixer", "mixer"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Planetary Mixer" if "planetary" in cap_lower or "planetari" in cap_lower else "Mixer Adonan Roti"
    elif any(k in cap_lower for k in ["meat grinder", "gilingan daging", "penggiling daging"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Meat Grinder Penggiling Daging"
    elif any(k in cap_lower for k in ["meat slicer", "pemotong daging", "slicer daging"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Meat Slicer Komersial"
    elif any(k in cap_lower for k in ["bone saw", "pemotong tulang", "gergaji tulang"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Bone Saw Mesin Potong Tulang"
    elif any(k in cap_lower for k in ["cup sealer", "sealer cup", "press cup"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Cup Sealer Mesin Press"
    elif any(k in cap_lower for k in ["vacuum sealer", "vacuum packaging", "vakum sealer", "mesin vakum"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Vacuum Sealer Komersial"
    elif any(k in cap_lower for k in ["band sealer", "continuous band", "mesin sealer"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Continuous Band Sealer"
    elif any(k in cap_lower for k in ["dough divider", "pembagi adonan", "proofer", "proofing box"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Mesin Proofer Bakery" if "proof" in cap_lower else "Dough Divider Pembagi Adonan"
    elif any(k in cap_lower for k in ["microwave", "gelombang mikro"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Microwave Komersial"
    elif any(k in cap_lower for k in ["blender komersial", "heavy duty blender"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Heavy Duty Commercial Blender"
    elif any(k in cap_lower for k in ["ompreng", "food pan", "pengering ompreng", "sterilizer"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Mesin Pengering Ompreng" if "pengering" in cap_lower else "Food Pan Ompreng Stainless"
    elif any(k in cap_lower for k in ["gelas", "wadah sendok", "piring", "mangkok"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Peralatan Makan & Minum Komersial"
    elif any(k in cap_lower for k in ["kursi", "meja makan", "meja cafe", "sofa", "meja kasir", "stand kayu", "lemari besi"]):
        cat_slug = "peralatan-dapur-bekas-lainnya"
        nama_alat = "Furniture Resto & Cafe"

    # Rule 9: Fallback / Uncertain
    else:
        confidence = "LOW"
        uncertainty_reason = "Kategori tidak teridentifikasi kata kunci standar."

    # 5. Binary Condition & Sub-Components
    kondisi_eval, sub_baru = evaluate_condition_binary(sanitized)
    is_baru_unit = (kondisi_eval == "Baru Sisa Proyek" or "BARU" in kondisi_eval.upper())
    kondisi_label = "Baru" if is_baru_unit else "Second"

    # 6. Build Title (Clean, NO "sisa proyek")
    parts = [nama_alat]
    is_fabrication = any(k in nama_alat.lower() for k in FABRICATION_KEYWORDS)
    if brand and not is_fabrication and brand.lower() not in nama_alat.lower():
        parts.append(brand)
    
    parts.append(kondisi_label)
    if dimensi and dimensi.lower() not in nama_alat.lower():
        parts.append(dimensi)

    title_clean = " ".join(parts)
    title_clean = re.sub(r'(?i)(?:sisa\s*proyek|ex\s*display|like\s*new|gress)', '', title_clean)
    title_clean = re.sub(r'\s+', ' ', title_clean).strip()

    # 7. Modal & Pricing
    modal = extract_modal_regex(sanitized)

    # 8. Sacred Slug vs Unique Slug
    if existing_slug and str(existing_slug).strip():
        slug = str(existing_slug).strip()
    else:
        slug_raw = re.sub(r'[^a-z0-9]+', '-', title_clean.lower()).strip('-')
        slug = f"{slug_raw}-{sku.lower()}"

    # Flag reasons for review
    is_stainless = any(k in cat_slug for k in ["meja", "sink", "rak", "hood", "wallshelf", "kabinet"])
    missing_dim = is_stainless and not dimensi

    return {
        "sku": sku,
        "title": title_clean,
        "nama_alat": nama_alat,
        "brand": brand,
        "dimensi": dimensi,
        "category_slug": cat_slug,
        "kondisi_unit": "Baru" if is_baru_unit else "Bekas Siap Pakai",
        "kondisi_tag": kondisi_label,
        "sub_komponen_baru": sub_baru,
        "status_unit": "SOLD" if any(k in cap_lower for k in ["sold", "laku", "terjual", "habis"]) else "READY",
        "harga_modal": modal,
        "slug": slug,
        "is_non_product": is_non_product,
        "confidence": confidence,
        "uncertainty_reason": uncertainty_reason,
        "missing_dimension": missing_dim,
        "caption_raw": caption,
        "source_group": source_group,
    }

# ==============================================================================
# MAIN AUDIT RUNNER
# ==============================================================================

def run_audit():
    print(f"=== BBKitchen Pure Regex MVP Catalog Auditor ===")
    print(f"Reading database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Read existing product slugs to respect Sacred Slug Lock
    prod_rows = cur.execute("SELECT sku, slug FROM products").fetchall()
    slug_map = {r["sku"]: r["slug"] for r in prod_rows if r["slug"]}

    # Read all raw records
    raw_rows = cur.execute("SELECT kode_unit, source_group, caption_raw, link_message FROM raw_pipeline ORDER BY CAST(SUBSTR(kode_unit, 4) AS INTEGER) ASC").fetchall()
    total = len(raw_rows)
    print(f"Total Raw Records to Audit: {total}")

    results = []
    klaster_low_confidence = []
    klaster_peralatan_lainnya = []
    klaster_missing_dim = []
    klaster_kondisi_baru = []
    klaster_non_product = []
    klaster_zero_modal = []

    for idx, r in enumerate(raw_rows, 1):
        sku = r["kode_unit"]
        caption = r["caption_raw"] or ""
        source_grp = r["source_group"] or ""
        link_msg = r["link_message"] or ""
        existing_slug = slug_map.get(sku)

        parsed = parse_regex_mvp(caption, sku, existing_slug=existing_slug, source_group=source_grp, link_msg=link_msg)
        results.append(parsed)

        if parsed["is_non_product"]:
            klaster_non_product.append(parsed)
        elif parsed["confidence"] == "LOW":
            klaster_low_confidence.append(parsed)
        elif parsed["category_slug"] == "peralatan-dapur-bekas-lainnya":
            klaster_peralatan_lainnya.append(parsed)

        if parsed["missing_dimension"] and not parsed["is_non_product"]:
            klaster_missing_dim.append(parsed)
        if parsed["kondisi_tag"] == "Baru" or parsed["sub_komponen_baru"]:
            klaster_kondisi_baru.append(parsed)
        if not parsed["harga_modal"] and not parsed["is_non_product"]:
            klaster_zero_modal.append(parsed)

    high_confidence_count = total - len(klaster_low_confidence) - len(klaster_non_product)

    # Generate Markdown Review Document
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# 📋 BBKitchen Pure Regex MVP Catalog Audit & Anomaly Review Report\n")
        f.write(f"> **Generated:** {time.strftime('%Y-%m-%d %H:%M:%S WIB')} | **Total Records:** {total} SKUs\n\n")
        f.write("Laporan ini menyajikan hasil batch normalisasi deterministik murni (Pure Regex MVP) pada 3.147 data mentah katalog BBKitchen tanpa biaya AI. Laporan ini mengelompokkan anomali dan kasus tepi yang siap ditinjau dan diklarifikasi oleh Principal.\n\n")
        f.write("---\n\n")
        f.write("## 📊 1. Ringkasan Eksekutif Hasil Normalisasi Regex\n\n")
        f.write(f"| Metrik Audit | Jumlah SKU | Persentase | Status Eksekusi |\n")
        f.write(f"| :--- | :---: | :---: | :--- |\n")
        f.write(f"| **Total Data Mentah (raw_pipeline)** | **{total}** | 100% | Selesai Dipindai |\n")
        f.write(f"| **Kategori SSOT Presisi Tinggi (57 Kategori Inti)** | **{high_confidence_count - len(klaster_peralatan_lainnya)}** | {round((high_confidence_count - len(klaster_peralatan_lainnya))/total*100, 1)}% | 🟢 Siap Batch Apply |\n")
        f.write(f"| **Mesin Olah Makanan / Bakery / Pendukung (Peralatan Lainnya)** | **{len(klaster_peralatan_lainnya)}** | {round(len(klaster_peralatan_lainnya)/total*100, 1)}% | 🟢 Valid SSOT (Lainnya) |\n")
        f.write(f"| **Kategori Tidak Dikenali / Low Confidence** | **{len(klaster_low_confidence)}** | {round(len(klaster_low_confidence)/total*100, 1)}% | 🟡 Perlu Klarifikasi User |\n")
        f.write(f"| **Unit Stainless Tanpa Angka Dimensi** | **{len(klaster_missing_dim)}** | {round(len(klaster_missing_dim)/total*100, 1)}% | ℹ️ Gunakan Standard Fallback |\n")
        f.write(f"| **Unit Berstatus 'Baru' / Komponen Refurbished** | **{len(klaster_kondisi_baru)}** | {round(len(klaster_kondisi_baru)/total*100, 1)}% | 🔍 Verifikasi Biner |\n")
        f.write(f"| **Terdeteksi Non-Produk / Iklan / Jasa / Loker** | **{len(klaster_non_product)}** | {round(len(klaster_non_product)/total*100, 1)}% | ⚪ Skip / Exclude dari Publik |\n")
        f.write(f"| **Harga Modal Nol / Tidak Disebutkan di Caption** | **{len(klaster_zero_modal)}** | {round(len(klaster_zero_modal)/total*100, 1)}% | 🛡️ Auto Anchor Dynamic Margins |\n\n")
        f.write("---\n\n")

        # Klaster 1: Non-Product
        f.write("## ⚪ 2. Klaster 1: Data Terdeteksi Non-Produk (Disarankan Skip)\n")
        f.write("> Data berikut terdeteksi sebagai pengumuman jasa, iklan ekspedisi, mesin kantor, atau lemari loker bukan peralatan dapur.\n\n")
        for item in klaster_non_product:
            f.write(f"### 📌 [{item['sku']}] Non-Produk\n")
            f.write(f"- **Caption Asli:** `{item['caption_raw']}`\n")
            f.write(f"- **Rekomendasi:** Tandai `status_pipeline = 'SKIP_NON_PRODUCT'` agar tidak muncul di web publik maupun sitemap.\n\n")

        # Klaster 2: Low Confidence (Truly Ambiguous)
        f.write("---\n\n")
        f.write(f"## 🟡 3. Klaster 2: Item Tidak Dikenali / Butuh Klarifikasi Kategori ({len(klaster_low_confidence)} SKU)\n")
        f.write("> Item-item ini tidak memuat kata kunci standar dari 58 kategori SSOT Horeca. Mohon tentukan kategori yang tepat atau konfirmasi apakah masuk 'peralatan-dapur-bekas-lainnya'.\n\n")
        for item in klaster_low_confidence:
            f.write(f"### 📌 [{item['sku']}] {item['title']}\n")
            f.write(f"- **Caption Asli:** `{item['caption_raw']}`\n")
            f.write(f"- **Hasil Regex Saat Ini:** Kategori: `{item['category_slug']}` | Judul: `{item['title']}`\n")
            f.write(f"- **Pertanyaan Review:** _Apakah unit ini masuk ke kategori kompor / meja / chiller / atau dibiarkan di kategori lainnya?_\n\n")

        # Klaster 3: Mesin Pendukung & Bakery (Peralatan Lainnya)
        f.write("---\n\n")
        f.write(f"## ⚙️ 4. Klaster 3: Mesin Olah Makanan, Bakery & Pendukung ({len(klaster_peralatan_lainnya)} SKU)\n")
        f.write("> Item-item ini berhasil diidentifikasi spesifikasinya (Mixer, Meat Grinder, Bone Saw, Cup Sealer, Troli Bakery, dsb.) dan secara resmi dikelompokkan ke kategori SSOT `peralatan-dapur-bekas-lainnya`.\n\n")
        for item in klaster_peralatan_lainnya[:25]:
            f.write(f"- **[{item['sku']}]** `{item['title']}` — Dimensi: `{item['dimensi'] or 'N/A'}` | Modal: `{format_rupiah(item['harga_modal'])}`\n")
        if len(klaster_peralatan_lainnya) > 25:
            f.write(f"\n_...dan {len(klaster_peralatan_lainnya) - 25} unit mesin olah makanan lainnya._\n\n")

        # Klaster 4: Stainless Units Missing Dimensions
        f.write("---\n\n")
        f.write(f"## 📏 5. Klaster 4: Unit Stainless Tanpa Angka Dimensi ({len(klaster_missing_dim)} SKU)\n")
        f.write("> Unit meja/sink/rak ini tidak memiliki rincian ukuran PxLxT pada caption gudang.\n\n")
        for item in klaster_missing_dim[:20]:
            f.write(f"- **[{item['sku']}]** `{item['title']}` | Caption: _{item['caption_raw'][:80]}..._\n")

        # Klaster 5: Kondisi Baru vs Komponen Baru
        f.write("---\n\n")
        f.write(f"## 🔍 6. Klaster 5: Unit 'Baru Sisa Proyek' vs Komponen Refurbished ({len(klaster_kondisi_baru)} SKU)\n")
        f.write("> Algoritma Layer 2 berhasil membedakan unit bekas dengan komponen baru (misal: 'Filter Baru', 'Burner Baru') vs unit utuh 'Baru'.\n\n")
        for item in klaster_kondisi_baru[:25]:
            sub_info = f"Komponen Baru: {item['sub_komponen_baru']}" if item['sub_komponen_baru'] else "Unit Baru Utuh"
            f.write(f"- **[{item['sku']}]** `{item['title']}` ➔ Status: **{item['kondisi_tag']}** ({sub_info})\n")

    conn.close()
    print(f"\n✅ Audit Finished Successfully!")
    print(f"Report Generated at: {REPORT_PATH}")
    print(f"Total Data: {total} | Core Categories: {high_confidence_count - len(klaster_peralatan_lainnya)} | Miscellaneous Valid: {len(klaster_peralatan_lainnya)} | Low Confidence: {len(klaster_low_confidence)} | Missing Dim: {len(klaster_missing_dim)}")

if __name__ == "__main__":
    import time
    run_audit()
