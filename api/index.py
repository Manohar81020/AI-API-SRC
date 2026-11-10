from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import json
import os
import requests

# ============================================================
# CONFIGURATION - ENV VARIABLES SE LOAD HOTA HAI
# ============================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
OXION_API_KEY = os.environ.get("OXION_API_KEY", "cc_rjDUDm7EloVSbHEhvl52qsrMMbiZS8jBLuNEn9GvLfJxN6vt")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "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")

# Optional: Oxion par ek specific model force karna ho to set karo
OXION_MODEL = os.environ.get("OXION_MODEL", "")

CREDIT = "@SHADOW_VIP_OWNER"

# Free models list (fallback order)
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]

OPENROUTER_MODELS = [
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
]

OXION_BASE = "https://www.oxionai.com/v1"

# Agar /models call fail ho jaye to ye IDs try honge
OXION_FALLBACK_MODELS = [
    "claude-opus-4.8",
]

TIMEOUT = 30

# Warm instance par resolve kiye gaye Oxion models yaad rakhta hai
_oxion_model_cache = []


# ============================================================
# PROVIDER FUNCTIONS
# ============================================================
def call_groq(question, model):
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY missing")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    if r.status_code != 200:
        raise Exception(f"Groq {model}: HTTP {r.status_code} - {r.text[:150]}")
    data = r.json()
    return data["choices"][0]["message"]["content"], f"groq:{model}"


def oxion_models():
    """Oxion se available chat models ki list laata hai (cached)."""
    global _oxion_model_cache
    if _oxion_model_cache:
        return _oxion_model_cache

    if OXION_MODEL:
        _oxion_model_cache = [OXION_MODEL]
        return _oxion_model_cache

    try:
        r = requests.get(
            f"{OXION_BASE}/models",
            headers={"Authorization": f"Bearer {OXION_API_KEY}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", []) if isinstance(data, dict) else []
            ids = [
                m["id"]
                for m in items
                if isinstance(m, dict) and m.get("id") and m.get("type", "chat") == "chat"
            ]
            if ids:
                _oxion_model_cache = ids[:4]
                return _oxion_model_cache
    except Exception:
        pass

    _oxion_model_cache = list(OXION_FALLBACK_MODELS)
    return _oxion_model_cache


def call_oxion(question, model):
    if not OXION_API_KEY:
        raise Exception("OXION_API_KEY missing")
    url = f"{OXION_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OXION_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    if r.status_code != 200:
        raise Exception(f"Oxion {model}: HTTP {r.status_code} - {r.text[:150]}")
    data = r.json()
    msg = data["choices"][0]["message"]
    text = msg.get("content") or msg.get("reasoning_content") or ""
    if not text:
        raise Exception(f"Oxion {model}: empty response")
    return text, f"oxion:{model}"


def call_openrouter(question, model):
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY missing")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://vercel.app",
        "X-Title": "Multi-AI API",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    if r.status_code != 200:
        raise Exception(f"OpenRouter {model}: HTTP {r.status_code} - {r.text[:150]}")
    data = r.json()
    return data["choices"][0]["message"]["content"], f"openrouter:{model}"


# ============================================================
# MAIN FALLBACK LOGIC
# ============================================================
def ask_ai(question):
    errors = []

    # Strategy 1: Groq (fastest)
    for model in GROQ_MODELS:
        try:
            text, source = call_groq(question, model)
            return text, source, errors
        except Exception as e:
            errors.append(str(e))

    # Strategy 2: Oxion (OpenAI-compatible)
    for model in oxion_models():
        try:
            text, source = call_oxion(question, model)
            return text, source, errors
        except Exception as e:
            errors.append(str(e))

    # Strategy 3: OpenRouter
    for model in OPENROUTER_MODELS:
        try:
            text, source = call_openrouter(question, model)
            return text, source, errors
        except Exception as e:
            errors.append(str(e))

    return None, None, errors


def active_providers():
    return {
        "groq": bool(GROQ_API_KEY),
        "oxion": bool(OXION_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
    }


# ============================================================
# HANDLER
# ============================================================
class handler(BaseHTTPRequestHandler):
    def _send(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {"status": True, "response": "OK", "credit": CREDIT})

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path.lstrip("/")
            qs = parse_qs(parsed.query)

            # Root / health check
            if path == "" or path == "api" or path == "api/index.py":
                if "text" not in qs:
                    return self._send(200, {
                        "status": True,
                        "response": "Multi-AI API is alive. Use /api?text=your+question",
                        "providers": active_providers(),
                        "credit": CREDIT,
                    })

            # Support both /api?text=... and /text=...
            question = None
            if "text" in qs:
                question = qs["text"][0]
            elif path and path not in ("api", "api/index.py"):
                question = unquote(path)

            if not question or not question.strip():
                return self._send(400, {
                    "status": False,
                    "response": "Missing 'text' parameter. Example: /api?text=hello",
                    "credit": CREDIT,
                })

            question = question.strip()

            text, source, errors = ask_ai(question)

            if text is None:
                return self._send(503, {
                    "status": False,
                    "response": "All providers failed. Check API keys / quota.",
                    "errors": errors[:5],
                    "credit": CREDIT,
                })

            return self._send(200, {
                "status": True,
                "response": text,
                "model": source,
                "credit": CREDIT,
            })

        except Exception as e:
            return self._send(500, {
                "status": False,
                "response": f"Internal error: {str(e)}",
                "credit": CREDIT,
            })

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                data = json.loads(raw)
            except Exception:
                data = {}

            question = data.get("text") or data.get("question") or data.get("prompt")
            if not question:
                return self._send(400, {
                    "status": False,
                    "response": "Missing 'text' in JSON body",
                    "credit": CREDIT,
                })

            text, source, errors = ask_ai(question.strip())
            if text is None:
                return self._send(503, {
                    "status": False,
                    "response": "All providers failed.",
                    "errors": errors[:5],
                    "credit": CREDIT,
                })

            return self._send(200, {
                "status": True,
                "response": text,
                "model": source,
                "credit": CREDIT,
            })
        except Exception as e:
            return self._send(500, {
                "status": False,
                "response": f"Internal error: {str(e)}",
                "credit": CREDIT,
            })
