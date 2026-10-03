# -*- coding: utf-8 -*-
"""
👑 BBKitchen Pure Gemini Multi-Tier AI Gateway (ai_gateway.py)
Unified Sovereign Multimodal Engine:
1. Primary: Google AI Studio Direct (Gemini Flash - Free Tier 1,500 RPD)
2. Fallback: Holver.id Gemini Gateway (gemini-3.8-flash / gemini-3.7-flash Vision)
3. Fail-Fast: Clean AIGatewayExhaustedError if both offline

Strictly pure Gemini family across both providers for 100% prompt & vision consistency.
"""

import os
import re
import json
import time
import requests
from typing import Dict, Any, Optional, List

def load_env(env_path=None):
    if env_path is not None and os.path.exists(env_path):
        candidates = [env_path]
    else:
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

class AIGatewayExhaustedError(RuntimeError):
    """Raised when all Gemini providers (Google Direct & Holver) are unavailable or quota-exhausted."""
    pass

def clean_json_text(raw_text: str) -> str:
    """Strips Markdown fences like ```json ... ``` from response."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

def parse_json_safely(raw_text: str) -> dict:
    cleaned = clean_json_text(raw_text)
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise

class AIGateway:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.holver_key = os.getenv("HOLVER_API_KEY", "")
        self.holver_base_url = os.getenv("HOLVER_BASE_URL", "https://api.holver.id/v1")

    def _call_google_gemini(self, prompt: str, image_base64_list: Optional[List[str]] = None, system_prompt: Optional[str] = None, model: str = "gemini-3.5-flash-lite") -> dict:
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not configured")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
        
        parts: List[Dict[str, Any]] = [{"text": prompt}]
        if image_base64_list:
            for b64 in image_base64_list:
                if b64:
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/webp",
                            "data": b64
                        }
                    })

        payload: Dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
                "maxOutputTokens": 2048
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        res = requests.post(url, json=payload, timeout=20)
        if res.status_code != 200:
            raise RuntimeError(f"Google Gemini Direct error {res.status_code}: {res.text[:200]}")
        
        data = res.json()
        raw_content = data["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json_safely(raw_content)

    def _call_holver_gemini(self, prompt: str, image_base64_list: Optional[List[str]] = None, system_prompt: Optional[str] = None, model: str = "gemini-3.8-flash") -> dict:
        if not self.holver_key:
            raise ValueError("HOLVER_API_KEY not configured")
        
        url = f"{self.holver_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.holver_key}",
            "Content-Type": "application/json"
        }
        
        user_content: Any = []
        user_content.append({"type": "text", "text": prompt})
        
        if image_base64_list:
            for b64 in image_base64_list:
                if b64:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/webp;base64,{b64}"}
                    })

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 2048
        }

        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code != 200:
            raise RuntimeError(f"Holver Gemini Gateway error {res.status_code}: {res.text[:200]}")
        
        data = res.json()
        raw_content = data["choices"][0]["message"]["content"]
        return parse_json_safely(raw_content)

    def _call_holver_text_workhorse(self, prompt: str, system_prompt: Optional[str] = None, model: str = "deepseek-4.1-flash") -> dict:
        if not self.holver_key:
            raise ValueError("HOLVER_API_KEY not configured")
        
        url = f"{self.holver_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.holver_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 2048
        }

        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code != 200:
            raise RuntimeError(f"Holver Text Workhorse error {res.status_code}: {res.text[:200]}")
        
        data = res.json()
        raw_content = data["choices"][0]["message"]["content"]
        return parse_json_safely(raw_content)

    def generate_vision_json(self, prompt: str, image_base64_list: Optional[List[str]] = None, system_prompt: Optional[str] = None) -> dict:
        """
        Executes prompt & optional photos strictly through Sovereign Cascade:
        1. Google AI Studio Direct (gemini-3.8-flash / gemini-2.5-flash-lite) [Primary Free Tier]
        2. Holver.id Gemini Gateway (gemini-3.8-flash / gemini-3.7-flash) [Sovereign Vision Proxy]
        3. Holver.id Sovereign Workhorse (deepseek-4.1-flash) [Text Fallback if Gemini quota depleted]
        """
        providers = [
            ("1a. Google AI Studio (gemini-3.5-flash-lite Direct)", lambda: self._call_google_gemini(prompt, image_base64_list, system_prompt, "gemini-3.5-flash-lite")),
            ("1b. Google AI Studio (gemini-3.5-flash Direct)", lambda: self._call_google_gemini(prompt, image_base64_list, system_prompt, "gemini-3.5-flash")),
            ("1c. Google AI Studio (gemini-3.7-flash Direct)", lambda: self._call_google_gemini(prompt, image_base64_list, system_prompt, "gemini-3.7-flash")),
            ("1d. Google AI Studio (gemini-flash-latest Direct)", lambda: self._call_google_gemini(prompt, image_base64_list, system_prompt, "gemini-flash-latest")),
            ("2a. Holver.id Gemini Gateway (gemini-3.8-flash)", lambda: self._call_holver_gemini(prompt, image_base64_list, system_prompt, "gemini-3.8-flash")),
            ("2b. Holver.id Gemini Gateway (gemini-3.7-flash)", lambda: self._call_holver_gemini(prompt, image_base64_list, system_prompt, "gemini-3.7-flash")),
            ("3. Holver.id Workhorse (deepseek-4.1-flash)", lambda: self._call_holver_text_workhorse(prompt, system_prompt, "deepseek-4.1-flash")),
        ]

        last_error = None
        for name, fn in providers:
            try:
                result = fn()
                if result and isinstance(result, dict):
                    return result
            except Exception as e:
                last_error = e
                time.sleep(0.3)

        raise AIGatewayExhaustedError(f"All AI Providers failed or exhausted! Last error: {last_error}")

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        """Text-only wrapper delegating to Pure Gemini Cascade."""
        return self.generate_vision_json(prompt, image_base64_list=None, system_prompt=system_prompt)

# Self-test
if __name__ == "__main__":
    gw = AIGateway()
    print("Testing Pure Gemini Gateway...")
    res = gw.generate_json(
        prompt="Sebutkan nama barang: 'Dijual Chiller 3 Pintu Sandev 180cm, harga 12.500.000 nego'. Return strictly JSON: {\"nama\": str, \"dimensi\": str}",
        system_prompt="Anda adalah AI Normalisasi BBKitchen. Return strictly JSON."
    )
    print("Gateway Result:", json.dumps(res, indent=2))
