import os
import json
import requests

def load_env(env_path=".env"):
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip("'").strip('"')

load_env()

# Test Gemini 2.5 Flash via native REST
gemini_key = os.getenv("GEMINI_API_KEY")
print("1. Testing Google AI Studio (gemini-2.5-flash)...")
try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    payload = {
        "contents": [{"parts": [{"text": "Return strictly JSON: {\"status\": \"gemini_active\", \"message\": \"Google AI Studio Connected\"}"}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    r = requests.post(url, json=payload, timeout=15)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print("   Response:", data["candidates"][0]["content"]["parts"][0]["text"].strip())
    else:
        print("   Failed:", r.text[:200])
except Exception as e:
    print("   Error:", e)

# Test Groq Cloud via OpenAI-compatible REST
groq_key = os.getenv("GROQ_API_KEY")
print("\n2. Testing Groq Cloud (openai/gpt-oss-120b & qwen/qwen3.8-27b)...")
for model in ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]:
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Return strictly JSON: {\"status\": \"groq_active\"}"}],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"   Model: {model} -> Status: {r.status_code}")
        if r.status_code == 200:
            print("   Response:", r.json()["choices"][0]["message"]["content"].strip())
            break
        else:
            print("   Failed:", r.text[:150])
    except Exception as e:
        print("   Error:", e)

# Test Cerebras via OpenAI-compatible REST
cerebras_key = os.getenv("CEREBRAS_API_KEY")
print("\n3. Testing Cerebras (gpt-oss-120b & qwen-3.8-27b)...")
for model in ["gpt-oss-120b", "qwen-3.8-27b"]:
    try:
        url = "https://api.cerebras.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {cerebras_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Return strictly JSON: {\"status\": \"cerebras_active\"}"}],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"   Model: {model} -> Status: {r.status_code}")
        if r.status_code == 200:
            print("   Response:", r.json()["choices"][0]["message"]["content"].strip())
            break
        else:
            print("   Failed:", r.text[:150])
    except Exception as e:
        print("   Error:", e)
