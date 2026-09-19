"""Small server-side clients; bounded retries and no credentials in artifacts."""
from __future__ import annotations

import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CLAIM = {"type": "object", "properties": {"text": {"type": "string"},
         "evidence_ids": {"type": "array", "items": {"type": "string"}}},
         "required": ["text", "evidence_ids"], "additionalProperties": False}
ANALYSIS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "overview": CLAIM,
        "changes": {"type": "array", "items": CLAIM},
        "tensions": {"type": "array", "items": CLAIM},
        "watchpoints": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "question": {"type": "string"},
                "metric": {"type": "string", "enum": ["advancing_pct", "volume_ratio", "tail_loss_pct", "above_vwap_pct"]},
                "operator": {"type": "string", "enum": [">", "<", ">=", "<="]},
                "threshold": {"type": "number"},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
            }, "required": ["question", "metric", "operator", "threshold", "evidence_ids"],
        }},
    }, "required": ["overview", "changes", "tensions", "watchpoints"],
}


def generate(context: dict, prompt: str, provider: str, model: str, api_key: str) -> dict:
    user = json.dumps(context, ensure_ascii=False)
    if len(user) > 120000:
        raise ValueError("source context exceeds configured limit")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise ValueError("invalid model identifier")
    if provider == "gemini":
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192,
                                     "responseMimeType": "application/json", "responseJsonSchema": ANALYSIS_SCHEMA}}
        headers = {"x-goog-api-key": api_key}
    elif provider == "minimax":
        endpoint = "https://api.minimaxi.com/v1/chat/completions"
        body = {"model": model, "messages": [{"role": "system", "content": prompt},
                {"role": "user", "content": user}], "temperature": 0.3, "max_completion_tokens": 8192}
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        raise ValueError("unsupported provider")
    request = Request(endpoint, data=json.dumps(body).encode(), method="POST",
                      headers={**headers, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("oversized provider response")
            payload = json.loads(raw)
            break
        except HTTPError as exc:
            exc.close()
            if attempt == 2 or (exc.code != 429 and not 500 <= exc.code < 600):
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    if provider == "gemini":
        candidate = payload["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ValueError("incomplete Gemini response")
        text = "".join(part.get("text", "") for part in candidate["content"]["parts"] if not part.get("thought"))
    else:
        choice = payload["choices"][0]
        if choice.get("finish_reason", "stop") != "stop":
            raise ValueError("incomplete MiniMax response")
        text = re.sub(r"<think>.*?</think>", "", choice["message"]["content"], flags=re.DOTALL).strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
    return json.loads(text)
