"""
BBKitchen Multi-Provider AI Failover Gateway
Unified 4-Tier Provider Cascade:
1. OpenAI (gpt-4o-mini / gpt-4o)
2. Google AI Studio (Gemini 2.5 Flash / Flash Latest)
3. Groq Cloud (Llama 3.3 70B / Qwen 2.5 32B)
4. DeepSeek AI (deepseek-chat)

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
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")

    def _call_openai(self, prompt: str, system_prompt: str = None, model: str = "gpt-4o-mini") -> dict:
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
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
        }

        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code != 200:
            raise RuntimeError(f"OpenAI error {res.status_code}: {res.text[:200]}")
        
        data = res.json()
        raw_content = data["choices"][0]["message"]["content"]
        return parse_json_safely(raw_content)

    def _call_gemini(self, prompt: str, system_prompt: str = None, model: str = "gemini-2.5-flash") -> dict:
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

    def _call_groq(self, prompt: str, system_prompt: str = None, model: str = "llama-3.3-70b-versatile") -> dict:
        if not self.groq_key:
            raise ValueError("GROQ_API_KEY not configured")
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
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

    def _call_deepseek(self, prompt: str, system_prompt: str = None, model: str = "deepseek-chat") -> dict:
        if not self.deepseek_key:
            raise ValueError("DEEPSEEK_API_KEY not configured")
        
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.deepseek_key}",
            "Content-Type": "application/json"
        }
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

        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(f"DeepSeek error {res.status_code}: {res.text[:200]}")
        
        data = res.json()
        raw_content = data["choices"][0]["message"]["content"]
        return parse_json_safely(raw_content)

    def generate_json(self, prompt: str, system_prompt: str = None) -> dict:
        """
        Executes prompt through the strict 4-tier provider cascade:
        1. OpenAI (gpt-4o-mini)
        2. Google Gemini (gemini-2.5-flash / gemini-1.5-flash)
        3. Groq Cloud (llama-3.3-70b-versatile / openai/gpt-oss-120b)
        4. DeepSeek AI (deepseek-chat)
        """
        providers = [
            ("1. OpenAI (gpt-4o-mini)", lambda: self._call_openai(prompt, system_prompt, "gpt-4o-mini")),
            ("2. Google AI Studio (gemini-2.5-flash)", lambda: self._call_gemini(prompt, system_prompt, "gemini-2.5-flash")),
            ("2b. Google AI Studio (gemini-1.5-flash)", lambda: self._call_gemini(prompt, system_prompt, "gemini-1.5-flash")),
            ("3. Groq Cloud (llama-3.3-70b-versatile)", lambda: self._call_groq(prompt, system_prompt, "llama-3.3-70b-versatile")),
            ("3b. Groq Cloud (openai/gpt-oss-120b)", lambda: self._call_groq(prompt, system_prompt, "openai/gpt-oss-120b")),
            ("4. DeepSeek AI (deepseek-chat)", lambda: self._call_deepseek(prompt, system_prompt, "deepseek-chat")),
        ]

        last_error = None
        for name, fn in providers:
            try:
                result = fn()
                if result and isinstance(result, dict):
                    return result
            except Exception as e:
                # Silently catch and log provider failover
                last_error = e
                time.sleep(0.3)

        raise RuntimeError(f"All 4 AI Providers failed! Last error: {last_error}")

# Quick test if run directly
if __name__ == "__main__":
    gateway = AIGateway()
    print("Testing AIGateway 4-Tier Cascade...")
    res = gateway.generate_json(
        prompt="Sebutkan nama barang: 'Dijual Chiller 3 Pintu Sandev 180cm, harga 12.500.000 nego, kondisi mulus'. Ekstrak nama, merk, dan dimensi.",
        system_prompt="Anda adalah AI Normalisasi BBKitchen. Ekstrak data dan kembalikan strictly JSON dengan format: {\"nama\": str, \"merk\": str, \"dimensi\": str}"
    )
    print("Gateway Result:", json.dumps(res, indent=2))
