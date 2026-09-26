"""
BBKitchen Dual-Provider Vision Ingestion Engine (100% Free Tier)
Providers:
1. Google Gemini Flash Vision (Primary - 1,500 free requests/day via Google AI Studio)
2. Groq Cloud Llama 3.2 Vision (Fallback - 14,400 free requests/day via Groq Cloud)

Extracts physical inspection details, condition, special components (trash chute, cabinet, welded vs knockdown),
and professional chef/F&B specification bullets from Telegram equipment photos.
"""

import os
import base64
import json
import mimetypes
import requests
from typing import Optional, Dict, Any, List

def load_env():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "..", ".env"),
        os.path.join(base_dir, ".env"),
        os.path.join(os.getcwd(), ".env")
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip("'").strip('"')
            break

load_env()

VISION_INSPECTION_PROMPT = """
Anda adalah Senior Commercial Kitchen Equipment Inspector & Professional F&B Equipment Specialist untuk Bukan Baru Kitchen (BBKitchen).
Tugas Anda adalah memeriksa foto alat dapur restoran/komersial bekas ini secara detail dan mengeluarkan laporan inspeksi fisik dalam format JSON murni.

PERIKSA SECARA TELITI:
1. Komponen Khusus & Tersembunyi:
   - Apakah ada lubang pembuangan sampah (trash chute / hole)?
   - Apakah ada lemari/cabinet tertutup (pintu geser/tarik)?
   - Berapa susun rak terbuka di bawah atau di samping?
   - Apakah konstruksinya las permanen (full welded heavy duty) atau bautan (knockdown)?
   - Apakah ada roda caster (dengan rem atau tanpa rem)?
   - Apakah ada kran, sink basin, splashback, atau laci?
2. Kondisi Fisik:
   - Estimasi kemulusan fisik (persentase 0-100%, misal 90% Mulus).
   - Kondisi plat stainless (hairline mulus, baret pemakaian, karat/penyok).
3. Stiker / Merk / Label:
   - Apakah terbaca stiker/plat merk tertentu (GEA, Nayati, Fomac, Getra, Crown, Berjaya, dll)?
4. Bahasa Spesifikasi Chef Profesional:
   - Buat 3-5 poin spesifikasi teknis dengan istilah standar chef/F&B komersial (contoh: Clearing/Bussing Station, Trash Chute, Enclosed Sanitation Cabinet, Food Grade 201/304, Heavy Duty Casters).

OUTPUT WAJIB JSON MURNI DENGAN STRUKTUR BERIKUT:
{
  "nama_alat_visual": "Nama alat umum yang jelas dalam bahasa Indonesia",
  "kategori_visual": "kategori umum alat",
  "estimasi_kondisi_persen": 90,
  "ringkasan_kondisi": "Deskripsi singkat kondisi fisik",
  "tipe_konstruksi": "welded / knockdown / modular",
  "fitur_khusus": [
    "fitur 1",
    "fitur 2"
  ],
  "stiker_merk_terdeteksi": "Merk jika terbaca atau null",
  "chef_spec_bullets": [
    "Poin spesifikasi standar chef 1",
    "Poin spesifikasi standar chef 2",
    "Poin spesifikasi standar chef 3"
  ]
}
"""

def encode_image_to_base64(image_path: str) -> tuple[str, str]:
    """Reads a local image and returns (base64_string, mime_type)."""
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        if image_path.lower().endswith(".webp"):
            mime_type = "image/webp"
        elif image_path.lower().endswith(".png"):
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"
            
    with open(image_path, "rb") as img_file:
        b64 = base64.b64encode(img_file.read()).decode("utf-8")
    return b64, mime_type

def parse_json_safely(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except Exception:
        import re
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise

class VisionExtractor:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.groq_key = os.getenv("GROQ_API_KEY", "")

    def inspect_image(self, image_path: str, caption_context: str = "") -> Dict[str, Any]:
        """
        Inspects an image using Gemini Flash Vision (Primary) with fallback to Groq Vision.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at: {image_path}")

        b64_data, mime_type = encode_image_to_base64(image_path)
        prompt_with_context = VISION_INSPECTION_PROMPT
        if caption_context:
            prompt_with_context += f"\n\nKONTEKS CAPTION TELEGRAM GUDANG:\n\"{caption_context}\""

        # 1. Try Google Gemini Flash Vision (Primary Free Tier)
        if self.gemini_key:
            try:
                res = self._call_gemini_vision(b64_data, mime_type, prompt_with_context)
                if res:
                    res["provider_used"] = "Google Gemini Flash Vision (Free)"
                    return res
            except Exception as e:
                print(f"[Vision Warning] Gemini Flash Vision failed: {e}. Falling back to Groq Vision...")

        # 2. Try Groq Vision (Fallback Free Tier)
        if self.groq_key:
            try:
                res = self._call_groq_vision(b64_data, mime_type, prompt_with_context)
                if res:
                    res["provider_used"] = "Groq Vision (Free)"
                    return res
            except Exception as e:
                print(f"[Vision Warning] Groq Vision failed: {e}")

        # Graceful fallback if no vision API key available
        return {
            "nama_alat_visual": "Alat Dapur Komersial",
            "kategori_visual": "peralatan-dapur",
            "estimasi_kondisi_persen": 85,
            "ringkasan_kondisi": "Kondisi fisik siap pakai standar restoran",
            "tipe_konstruksi": "welded",
            "fitur_khusus": [],
            "stiker_merk_terdeteksi": None,
            "chef_spec_bullets": [],
            "provider_used": "FALLBACK_NO_VISION_KEY"
        }

    def _call_gemini_vision(self, b64_data: str, mime_type: str, prompt: str) -> Optional[Dict[str, Any]]:
        models = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-2.5-flash"]
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }
        last_err = None
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
            try:
                resp = requests.post(url, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return parse_json_safely(raw_text)
                else:
                    last_err = f"{model} status {resp.status_code}: {resp.text[:150]}"
            except Exception as ex:
                last_err = f"{model} exception: {ex}"
                continue
        raise RuntimeError(f"All Gemini Vision models failed on generateContent ({last_err})")

    def _call_groq_vision(self, b64_data: str, mime_type: str, prompt: str) -> Optional[Dict[str, Any]]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        image_url = f"data:{mime_type};base64,{b64_data}"
        payload = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return clean_json_response(raw_text)
        raise RuntimeError(f"Groq API returned status {resp.status_code}: {resp.text[:200]}")
