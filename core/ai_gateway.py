"""
BBKitchen Multi-Provider AI Failover Gateway
Supports Google AI Studio (Gemini 3.6 Flash / Flash Latest) and Groq Cloud (GPT-OSS-120B / Qwen 3.8 27B)
Zero external SDK dependencies (pure requests + json), robust failover and strict JSON schema return.
"""

import os
import re
import json
import time
import requests

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
        # Fallback: regex search for outer {...}
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise

class AIGateway:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.groq_key = os.getenv("GROQ_API_KEY", "")

    def _call_gemini(self, prompt: str, system_prompt: str = None, model: str = "gemini-3.6-flash") -> dict:
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not configured")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        res = requests.post(url, json=payload, timeout=25)
        if res.status_code != 200:
            raise RuntimeError(f"Gemini error {res.status_code}: {res.text[:200]}")
        
        data = res.json()
        raw_content = data["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json_safely(raw_content)

    def _call_groq(self, prompt: str, system_prompt: str = None, model: str = "openai/gpt-oss-120b") -> dict:
        if not self.groq_key:
            raise ValueError("GROQ_API_KEY not configured")
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        # Ensure 'json' is explicitly in prompt for Groq strict compliance
        guaranteed_prompt = prompt if "json" in prompt.lower() else f"{prompt}\n\nRespond strictly in valid JSON format."
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": guaranteed_prompt})

        payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1500
        }

        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code != 200:
            raise RuntimeError(f"Groq error {res.status_code}: {res.text[:200]}")
        
        data = res.json()
        raw_content = data["choices"][0]["message"]["content"]
        return parse_json_safely(raw_content)

    def generate_json(self, prompt: str, system_prompt: str = None) -> dict:
        """
        Executes prompt through the failover provider pool:
        1. Google Gemini 3.6 Flash
        2. Groq Cloud (GPT-OSS-120B)
        3. Groq Cloud (Qwen 3.8 27B)
        4. Google Gemini Flash Latest
        """
        providers = [
            ("Google AI Studio (gemini-3.6-flash)", lambda: self._call_gemini(prompt, system_prompt, "gemini-3.6-flash")),
            ("Groq Cloud (gpt-oss-120b)", lambda: self._call_groq(prompt, system_prompt, "openai/gpt-oss-120b")),
            ("Groq Cloud (qwen3.8-27b)", lambda: self._call_groq(prompt, system_prompt, "qwen/qwen3.8-27b")),
            ("Google AI Studio (gemini-flash-latest)", lambda: self._call_gemini(prompt, system_prompt, "gemini-flash-latest")),
        ]

        last_error = None
        for name, fn in providers:
            try:
                # print(f"  [AI Gateway] Trying {name}...")
                result = fn()
                if result and isinstance(result, dict):
                    return result
            except Exception as e:
                # print(f"  [AI Gateway Warning] {name} failed: {e}. Switching to fallback...")
                last_error = e
                time.sleep(0.5)

        raise RuntimeError(f"All AI Providers failed! Last error: {last_error}")

# Quick test if run directly
if __name__ == "__main__":
    gateway = AIGateway()
    print("Testing AIGateway...")
    res = gateway.generate_json(
        prompt="Sebutkan nama barang: 'Dijual Chiller 3 Pintu Sandev 180cm, harga 12.500.000 nego, kondisi mulus'. Ekstrak nama, merk, dan dimensi.",
        system_prompt="Anda adalah AI Normalisasi BBKitchen. Ekstrak data dan kembalikan strictly JSON dengan format: {\"nama\": str, \"merk\": str, \"dimensi\": str}"
    )
    print("Gateway Result:", json.dumps(res, indent=2))
