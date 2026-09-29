# -*- coding: utf-8 -*-
"""
👑 BBKitchen Sovereign Vision Photo Reconciliation Engine
Sub-Modul 2.11 / Task 2.11.5 - Autonomous Physical Photo Verification via Gemini 3.8 Flash
"""

import os
import sys
import json
import time
import base64
import sqlite3
import requests
import mimetypes
from typing import Dict, Any, Optional, List

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
for p in [CURRENT_DIR, PARENT_DIR]:
    if p not in sys.path:
        sys.path.append(p)

from ai_gateway import AIGateway, load_env
from normalize_engine import OFFICIAL_CATEGORY_SLUGS, CAT_SSOT

load_env()

CDN_BASE_URL = "https://assets.bukanbarukitchen.com/products"
WP_CDN_BASE_URL = "https://bukanbarukitchen.com/wp-content/uploads"

VISION_RECONCILE_PROMPT = """Anda adalah Senior Equipment Visual Inspector untuk BBKitchen (Penyedia Alat Dapur Resto Second Terbesar).
Tugas Anda: Memeriksa FOTO ALAT INI secara objektif dan mengekstrak jenis fisik alat yang sesungguhnya.

PERIKSA SECARA TELITI:
1. Apa nama alat dan kategori fisik yang tampak di foto? (misal: "Kompor Kwali 2 Burner", "Undercounter Chiller 2 Pintu", "Meja Stainless 2 Susun", "Exhaust Hood", "Single Sink").
2. Apakah tampak stiker/plat merk tertentu? (misal: GEA, Nayati, Fomac, Getra, Escoffier, atau Tanpa Merk/Fabrikasi).
3. Kondisi fisik yang terlihat (0-100% dan catatan fisik).
4. Fitur visual utama (misal: ada kompresor, ada bak cuci, ada roda, ada burner api, ada pintu geser).

KEMBALIKAN STRICTLY JSON DENGAN FORMAT:
{
  "nama_alat_visual": "Nama alat fisik yang terlihat jelas di foto",
  "kategori_visual_slug": "<pilih salah satu slug 66-SSOT yang paling cocok>",
  "merk_terlihat": "Nama brand jika terbaca di foto atau null",
  "estimasi_kondisi_persen": 85,
  "fitur_utama": ["fitur 1", "fitur 2"],
  "is_valid_kitchen_equipment": true,
  "catatan_inspeksi": "Deskripsi singkat penampakan visual"
}
"""

def fetch_image_base64_from_url(url: str) -> Optional[tuple[str, str]]:
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            content_type = res.headers.get("content-type", "image/webp")
            b64 = base64.b64encode(res.content).decode("utf-8")
            return b64, content_type
    except Exception as e:
        pass
    return None

def inspect_product_photo_vision(photo_filename_or_url: str, gateway: AIGateway) -> Optional[Dict[str, Any]]:
    # Resolve URL
    if photo_filename_or_url.startswith("http"):
        img_url = photo_filename_or_url
    else:
        clean_name = photo_filename_or_url.split(",")[0].strip()
        img_url = f"{CDN_BASE_URL}/{clean_name}"

    img_data = fetch_image_base64_from_url(img_url)
    if not img_data:
        # Fallback to local .temp_webp or archive if exists
        local_candidates = [
            os.path.join(PARENT_DIR, ".temp_webp", photo_filename_or_url),
            os.path.join(PARENT_DIR, photo_filename_or_url)
        ]
        for loc in local_candidates:
            if os.path.exists(loc):
                with open(loc, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                    img_data = (b64, "image/webp")
                break

    if not img_data:
        return {"error": "IMAGE_NOT_ACCESSIBLE", "url": img_url}

    b64_str, mime_type = img_data

    # Send to Holver Gemini 3.8 Flash Vision
    headers = {
        "Authorization": f"Bearer {gateway.holver_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gemini-3.8-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_RECONCILE_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_str}"}}
                ]
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    try:
        res = requests.post("https://api.holver.id/v1/chat/completions", headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            if content.startswith("```"):
                content = content.split("```")[1].replace("json", "").strip()
            return json.loads(content)
    except Exception as e:
        return {"error": str(e)}

    return None

if __name__ == "__main__":
    print("Testing Vision Photo Reconciler on sample unit...")
    gw = AIGateway()
    res = inspect_product_photo_vision("BBK0001_1.webp", gw)
    print("VISION RECONCILIATION RESULT:")
    print(json.dumps(res, indent=2))
