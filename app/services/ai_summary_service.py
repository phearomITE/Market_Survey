# app/services/ai_summary_service.py
from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.core.config import settings


JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "key_issues": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 4,
            "maxItems": 4,
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 4,
            "maxItems": 4,
        },
    },
    "required": ["key_issues", "suggestions"],
}


PREFERRED_SUMMARY_MODELS = [
    "qwen2.5:7b",
    "qwen3:8b",
    "llama3.1:8b",
    "deepseek-r1:8b",
    "deepseek-r1:1.5b",
]


def _clean_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value).replace("\r", "\n").strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_short(value: str) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    parts = re.split(r"(?:\n+|(?<=។)|(?<=\.)|(?<=;)|\s+[0-9]+[\.)]\s*)", text)
    out: list[str] = []
    for part in parts:
        clean = part.strip(" -•\t\n.។")
        if clean and clean not in out:
            out.append(clean)
    return out


def _first_four(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        for part in _split_short(value):
            if part and part not in out:
                out.append(part)
            if len(out) >= 4:
                return out[:4]
    while len(out) < 4:
        out.append("")
    return out[:4]


def _ensure_four(values: Any, fallback: list[str] | None = None) -> list[str]:
    if not isinstance(values, list):
        values = [str(values)] if values else []
    out: list[str] = []
    for value in values:
        text = _clean_text(value)
        text = re.sub(r"^\s*[0-9]+[\.)]\s*", "", text).strip()
        text = text.strip('"')
        if text and text not in out:
            out.append(text)
    if fallback:
        for value in _first_four(fallback):
            if value and value not in out:
                out.append(value)
            if len(out) >= 4:
                break
    while len(out) < 4:
        out.append("")
    return out[:4]


def _normalize_result(data: dict[str, Any], fallback_issues: list[str], fallback_suggestions: list[str]) -> dict[str, list[str]]:
    issues = data.get("key_issues") or data.get("issues") or data.get("keyIssues") or []
    suggestions = (
        data.get("suggestions")
        or data.get("initiative_suggestions")
        or data.get("initiatives")
        or data.get("initiativeIdeas")
        or []
    )
    return {
        "key_issues": _ensure_four(issues, fallback_issues),
        "suggestions": _ensure_four(suggestions, fallback_suggestions),
    }


def _compact_comments(texts: list[str], max_items: int = 35, max_chars_each: int = 420) -> list[str]:
    """Deduplicate user comments. This is NOT keyword analysis."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in texts:
        text = _clean_text(raw)
        if not text:
            continue
        key = re.sub(r"\s+", " ", text.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        if len(text) > max_chars_each:
            text = text[:max_chars_each].rstrip() + "..."
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def _compact_business_context(context: dict[str, Any] | None) -> str:
    """Small numeric context for AI. Python calculates metrics; AI summarizes text meaning."""
    if not context:
        return ""

    lines: list[str] = [
        f"Dealer: {context.get('dealer') or ''}",
        f"Region: {context.get('region') or ''}",
        f"Total outlet visits: {context.get('total_outlets') or 0}",
    ]

    products = context.get("products") or {}
    product_lines: list[str] = []
    for name, pdata in products.items():
        mov = pdata.get("mov")
        stock = pdata.get("stock")
        bbe = pdata.get("bbe")
        availability = pdata.get("availability") or {}
        avail_total = sum(int(v or 0) for v in availability.values()) if isinstance(availability, dict) else 0
        if any(x not in (None, "", 0) for x in [mov, stock, bbe, avail_total]):
            product_lines.append(f"- {name}: availability={avail_total}, avg_movement={mov or ''}, stock_summary={stock or ''}, dominant_BBE={bbe or ''}")
        if len(product_lines) >= 12:
            break
    if product_lines:
        lines.append("Product metrics:")
        lines.extend(product_lines)

    competitors = context.get("competitors") or {}
    competitor_lines: list[str] = []
    for name, cdata in competitors.items():
        mov = cdata.get("mov")
        if mov not in (None, "", 0):
            competitor_lines.append(f"- {name}: avg_movement={mov}")
        if len(competitor_lines) >= 10:
            break
    if competitor_lines:
        lines.append("Competitor metrics:")
        lines.extend(competitor_lines)

    ring = context.get("ring_pull") or {}
    ring_lines: list[str] = []
    for name, rdata in ring.items():
        if isinstance(rdata, dict):
            qty = rdata.get("qty")
            total_outlets = rdata.get("total_outlets")
            if qty not in (None, "", 0) or total_outlets not in (None, "", 0):
                ring_lines.append(f"- {name}: outlets={total_outlets or 0}, qty={qty or 0}")
    if ring_lines:
        lines.append("Ring Pull metrics:")
        lines.extend(ring_lines)

    return "\n".join(lines)


def _remove_thinking(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"(?is)^\s*thinking\.\.\..*?(?:\.\.\.done thinking\.|done thinking\.)", "", text).strip()
    text = text.strip("` \n\t")
    text = re.sub(r"^json\s*", "", text, flags=re.IGNORECASE).strip()
    first_brace = text.find("{")
    if first_brace > 0:
        text = text[first_brace:]
    return text.strip()


def _balanced_json_objects(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(text[start:i + 1])
                    start = None
    return candidates


def _extract_json(text: str) -> dict[str, Any]:
    if not text:
        raise ValueError("empty AI response")

    cleaned = _remove_thinking(text)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    for candidate in _balanced_json_objects(cleaned):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            continue

    repaired = cleaned.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    for candidate in _balanced_json_objects(repaired):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            continue

    # Very last resort: parse numbered lines if a model ignored JSON completely.
    key_match = re.search(r"key[_\s-]*issues?\s*[:\n](.*?)(?:suggestions?|initiative)", cleaned, re.I | re.S)
    sug_match = re.search(r"(?:suggestions?|initiative[^:\n]*)\s*[:\n](.*)$", cleaned, re.I | re.S)
    if key_match or sug_match:
        return {
            "key_issues": _split_short(key_match.group(1))[:4] if key_match else [],
            "suggestions": _split_short(sug_match.group(1))[:4] if sug_match else [],
        }

    preview = cleaned[:500].replace("\n", " ")
    raise ValueError(f"No valid JSON object found in AI response. Preview: {preview}")


def _build_prompt(key_issue_texts: list[str], suggestion_texts: list[str], business_context: dict[str, Any] | None) -> str:
    compact_issues = _compact_comments(key_issue_texts, max_items=35)
    compact_suggestions = _compact_comments(suggestion_texts, max_items=35)
    issue_block = "\n".join(f"Outlet comment {i+1}: {text}" for i, text in enumerate(compact_issues)) or "No key issue comments provided."
    suggestion_block = "\n".join(f"Suggestion comment {i+1}: {text}" for i, text in enumerate(compact_suggestions)) or "No suggestion comments provided."
    context_block = _compact_business_context(business_context)

    return f"""
You are a Cambodian Sales Manager for Khmer Beverages.
Your job is to write a short, clear management summary for ONE dealer.
The outlet comments may be Khmer, English, or mixed Khmer-English.

Writing style rules:
- Write like a real Cambodian sales manager, not like AI and not like copied survey text.
- Use simple Khmer, short words, and easy management language.
- Keep each point very short: one natural sentence only, about 6-12 words if possible.
- Merge repeated comments into one clear point.
- Mention only the most important products; do not list too many product names.
- Focus on business meaning: low stock, slow movement, competitor strong, freshness, or execution gap.
- Suggestions must be practical actions for SO/SA/sales team, written like a human manager.
- Do NOT copy raw outlet comments directly; rewrite them in clean easy Khmer.
- Do NOT mention outlet names, user names, IDs, phone numbers, or individual comment numbers.
- Do NOT invent information that is not supported by comments or metrics.
- English product names are OK.
- Return exactly 4 key_issues and exactly 4 suggestions.
- Each item must be concise, easy to read, and suitable for one Excel row.
- Return JSON only, no markdown, no explanation.

Business metrics calculated by Python:
{context_block}

Raw Key Issue comments:
{issue_block}

Raw Initiative / Suggestion comments:
{suggestion_block}

Return ONLY this JSON structure with filled values:
{{
  "key_issues": ["...", "...", "...", "..."],
  "suggestions": ["...", "...", "...", "..."]
}}
""".strip()


def _ollama_url(path: str) -> str:
    return f"{str(settings.ollama_base_url).rstrip('/')}{path}"


def _available_models(timeout: int = 10) -> list[str]:
    try:
        response = requests.get(_ollama_url("/api/tags"), timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception as exc:
        print(f"⚠️ Cannot read Ollama model list: {exc}")
        return []


def _select_model() -> str:
    configured = str(settings.ollama_model or "").strip()
    models = _available_models()
    if configured and (not models or configured in models):
        return configured
    for preferred in PREFERRED_SUMMARY_MODELS:
        if preferred in models:
            if configured and configured != preferred:
                print(f"⚠️ Configured OLLAMA_MODEL={configured} not found. Using installed model {preferred}.")
            return preferred
    return configured or "qwen2.5:7b"


def _read_chat_response(data: dict[str, Any]) -> str:
    msg = data.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if content not in (None, ""):
        return str(content)
    if data.get("response") not in (None, ""):
        return str(data.get("response"))
    return ""


def _post_chat(prompt: str, *, model: str, use_json_mode: bool, stream: bool, timeout: int) -> str:
    messages = [
        {"role": "system", "content": "You are a JSON-only market report summarization API. Return valid JSON only."},
        {"role": "user", "content": prompt},
    ]
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": float(settings.ai_summary_temperature or 0.1),
            "num_ctx": min(int(settings.ai_summary_num_ctx or 4096), 4096),
            "num_predict": 800,
        },
        "keep_alive": "15m",
    }
    if use_json_mode:
        payload["format"] = "json"

    response = requests.post(_ollama_url("/api/chat"), json=payload, timeout=timeout, stream=stream)
    response.raise_for_status()

    if not stream:
        return _read_chat_response(response.json()).strip()

    parts: list[str] = []
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except Exception:
            continue
        text = _read_chat_response(chunk)
        if text:
            parts.append(text)
    return "".join(parts).strip()


def _post_generate(prompt: str, *, model: str, use_json_mode: bool, timeout: int) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": float(settings.ai_summary_temperature or 0.1),
            "num_ctx": min(int(settings.ai_summary_num_ctx or 4096), 4096),
            "num_predict": 800,
        },
        "keep_alive": "15m",
    }
    if use_json_mode:
        payload["format"] = "json"
    response = requests.post(_ollama_url("/api/generate"), json=payload, timeout=timeout)
    response.raise_for_status()
    return str(response.json().get("response") or "").strip()


def _call_ollama(prompt: str) -> str:
    timeout = int(settings.ai_summary_timeout or 600)
    model = _select_model()
    print(f"🤖 Ollama summary request: model={model}, prompt_chars={len(prompt)}, timeout={timeout}")

    # generate_json first: most stable on Windows for Qwen/DeepSeek in this project.
    attempts = [
        ("generate_json", lambda: _post_generate(prompt, model=model, use_json_mode=True, timeout=timeout)),
        ("generate_plain", lambda: _post_generate(prompt, model=model, use_json_mode=False, timeout=timeout)),
        ("chat_json_nonstream", lambda: _post_chat(prompt, model=model, use_json_mode=True, stream=False, timeout=timeout)),
        ("chat_plain_nonstream", lambda: _post_chat(prompt, model=model, use_json_mode=False, stream=False, timeout=timeout)),
        ("chat_plain_stream", lambda: _post_chat(prompt, model=model, use_json_mode=False, stream=True, timeout=timeout)),
    ]

    last_error = ""
    for name, fn in attempts:
        try:
            text = fn()
            if text:
                print(f"✅ Ollama AI summary mode: {name}, chars={len(text)}")
                return text
            last_error = f"{name}: empty response"
            print(f"⚠️ Ollama attempt failed: {last_error}")
        except Exception as exc:
            last_error = f"{name}: {exc}"
            print(f"⚠️ Ollama attempt failed: {last_error}")
    raise ValueError(last_error or "empty AI response")



def _read_google_response(data: dict[str, Any]) -> str:
    """Read Gemini REST API text response safely.

    Gemini can return multiple candidates and multiple text parts. Read all of
    them instead of only candidates[0].content.parts[0].text.
    """
    if data.get("error"):
        raise ValueError(str(data.get("error")))

    texts: list[str] = []
    for cand in data.get("candidates") or []:
        content = cand.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict) and part.get("text") not in (None, ""):
                texts.append(str(part.get("text")))

    return "\n".join(texts).strip()


def _google_request_payload(prompt: str, *, json_mode: bool) -> dict[str, Any]:
    """Build a Gemini REST request.

    For Gemini 2.5 models, disable thinking budget when supported. Without this,
    small maxOutputTokens can be consumed by hidden thinking and the visible JSON
    may be incomplete/truncated.
    """
    system_instruction = (
        "You are a JSON-only market report summarization API for Khmer Beverages. "
        "Return ONLY valid JSON. No markdown. No explanations. No ``` fences."
    )
    strict_prompt = f"""
{prompt}

STRICT OUTPUT RULES:
Return ONLY one complete valid JSON object.
Do not use markdown.
Do not wrap with ```json.
Do not add explanation before or after JSON.
The JSON must contain exactly these keys:
{{
  "key_issues": ["...", "...", "...", "..."],
  "suggestions": ["...", "...", "...", "..."]
}}
""".strip()

    generation_config: dict[str, Any] = {
        "temperature": float(settings.ai_summary_temperature or 0.1),
        "maxOutputTokens": 2048,
        # Helps Gemini 2.5 Flash avoid spending tokens on thinking.
        "thinkingConfig": {"thinkingBudget": 0},
    }

    if json_mode:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = {
            "type": "OBJECT",
            "properties": {
                "key_issues": {"type": "ARRAY", "items": {"type": "STRING"}},
                "suggestions": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["key_issues", "suggestions"],
        }

    return {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": strict_prompt}],
            }
        ],
        "generationConfig": generation_config,
    }


def _call_google_gemini(prompt: str) -> str:
    """Use Google Gemini REST API for AI report summary.

    Production behavior:
    - Try JSON mode first.
    - If Gemini returns incomplete/non-JSON, retry with plain text mode.
    - If Gemini 2.5 model still fails, retry gemini-2.0-flash as a stable fallback.
    - Validate/parses JSON before returning to the caller.
    """
    api_key = str(getattr(settings, "google_api_key", "") or "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is empty")

    configured_model = str(getattr(settings, "google_model", "") or "gemini-2.0-flash").strip()
    timeout = int(settings.ai_summary_timeout or 600)

    model_candidates: list[str] = [configured_model]
    if configured_model != "gemini-2.0-flash":
        model_candidates.append("gemini-2.0-flash")

    last_error = ""
    for model in model_candidates:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for mode_name, json_mode in [("json_schema", True), ("plain_strict", False)]:
            try:
                payload = _google_request_payload(prompt, json_mode=json_mode)
                print(
                    f"🤖 Google Gemini summary request: model={model}, mode={mode_name}, "
                    f"prompt_chars={len(prompt)}, timeout={timeout}"
                )
                response = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                text = _read_google_response(data)

                # Diagnostic info for truncation/safety issues.
                finish_reasons = [c.get("finishReason") for c in (data.get("candidates") or []) if c.get("finishReason")]
                if finish_reasons:
                    print(f"ℹ️ Gemini finishReason={finish_reasons}")

                if not text:
                    raise ValueError("empty Google Gemini response")

                # Validate here. If invalid/incomplete, retry another mode/model.
                parsed = _extract_json(text)
                normalized = _normalize_result(parsed, [], [])
                if not any(normalized.get("key_issues") or []) and not any(normalized.get("suggestions") or []):
                    raise ValueError("Gemini JSON has empty key_issues and suggestions")

                print(f"✅ Google Gemini AI summary completed, mode={mode_name}, chars={len(text)}")
                return text
            except Exception as exc:
                last_error = f"{model}/{mode_name}: {exc}"
                print(f"⚠️ Google Gemini attempt failed: {last_error}")
                continue

    raise ValueError(last_error or "Google Gemini summary failed")


def summarize_with_ollama(
    key_issue_texts: list[str],
    suggestion_texts: list[str],
    business_context: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Use local Ollama model directly for final Key Issues/Suggestions.

    No THEMES and no keyword templates are used. Python calculates numeric
    metrics; the local AI summarizes Khmer/English comments into 4 + 4 lines.
    """
    fallback_issues = [_clean_text(x) for x in key_issue_texts if _clean_text(x)]
    fallback_suggestions = [_clean_text(x) for x in suggestion_texts if _clean_text(x)]

    if not getattr(settings, "ai_summary_enabled", False):
        return _normalize_result({}, fallback_issues, fallback_suggestions)
    if not fallback_issues and not fallback_suggestions:
        return _normalize_result({}, fallback_issues, fallback_suggestions)

    prompt = _build_prompt(fallback_issues, fallback_suggestions, business_context)
    provider = str(getattr(settings, "ai_provider", "ollama") or "ollama").strip().lower()
    try:
        if provider in {"google", "gemini", "google_gemini"}:
            try:
                text = _call_google_gemini(prompt)
            except Exception as google_exc:
                # Production-safe fallback to local Ollama if Google fails and Ollama is configured.
                print(f"⚠️ Google Gemini AI summary failed: {google_exc}")
                print("↪️ Trying local Ollama fallback...")
                text = _call_ollama(prompt)
        else:
            text = _call_ollama(prompt)

        data = _extract_json(text)
        normalized = _normalize_result(data, fallback_issues, fallback_suggestions)
        if any(normalized["key_issues"]) or any(normalized["suggestions"]):
            return normalized
        raise ValueError("AI returned empty key_issues and suggestions")
    except Exception as exc:
        # Production-safe: report generation must never crash if AI is unavailable.
        print(f"⚠️ AI summary unavailable, using clean raw-comment fallback: {exc}")
        return _normalize_result({}, fallback_issues, fallback_suggestions)
