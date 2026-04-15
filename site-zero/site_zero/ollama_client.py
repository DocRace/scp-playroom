"""Minimal Ollama HTTP client (compatible with ai-tabulation localhost setup)."""

from __future__ import annotations

import json
from typing import Any

import httpx


async def ollama_generate(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    *,
    timeout: float = 120.0,
    temperature: float = 0.4,
) -> str:
    url = f"{base_url.rstrip('/')}/api/generate"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    r = await client.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return str(data.get("response", ""))


async def ollama_embed(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    text: str,
    *,
    timeout: float = 60.0,
) -> list[float]:
    """Ollama /api/embeddings — use a dedicated embed model (e.g. nomic-embed-text)."""
    url = f"{base_url.rstrip('/')}/api/embeddings"
    payload: dict[str, Any] = {"model": model, "prompt": text}
    r = await client.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    emb = data.get("embedding")
    if not isinstance(emb, list):
        raise ValueError("invalid_embedding_response")
    return [float(x) for x in emb]


async def ollama_available(client: httpx.AsyncClient, base_url: str) -> bool:
    try:
        r = await client.get(f"{base_url.rstrip('/')}/api/tags", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_options(temperature: float, num_predict: int | None) -> dict[str, Any]:
    opts: dict[str, Any] = {"temperature": temperature}
    if num_predict is not None:
        opts["num_predict"] = int(num_predict)
    return opts


async def ollama_chat_json(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    timeout: float = 120.0,
    temperature: float = 0.25,
    num_predict: int | None = None,
) -> dict[str, Any]:
    """
    Ollama /api/chat with JSON mode — returns parsed object from assistant message.content.
    """
    url = f"{base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": _ollama_options(temperature, num_predict),
    }
    r = await client.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = data.get("message", {}).get("content", "")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str) or not content.strip():
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start : end + 1])
        raise


def ollama_chat_json_sync(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    timeout: float = 120.0,
    temperature: float = 0.2,
    num_predict: int | None = None,
) -> dict[str, Any]:
    """Synchronous /api/chat with JSON format — same behavior as ``ollama_chat_json``."""
    url = f"{base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": _ollama_options(temperature, num_predict),
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    content = data.get("message", {}).get("content", "")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str) or not content.strip():
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start : end + 1])
        raise


def ollama_generate_sync(
    base_url: str,
    model: str,
    prompt: str,
    *,
    timeout: float = 120.0,
    temperature: float = 0.2,
    json_mode: bool = False,
    num_predict: int | None = None,
) -> str:
    """Synchronous generate — used inside LangGraph sync nodes (SCP-079 planner)."""
    url = f"{base_url.rstrip('/')}/api/generate"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": _ollama_options(temperature, num_predict),
    }
    if json_mode:
        payload["format"] = "json"
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        return str(data.get("response", ""))


def parse_scp079_actions_json(raw: str) -> list[dict[str, Any]]:
    """Parse LLM output into [{\"tool\": str, \"params\": dict}, ...]."""
    text = raw.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            return []
    actions = data.get("actions") if isinstance(data, dict) else data
    if not isinstance(actions, list):
        return []
    out: list[dict[str, Any]] = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        tool = a.get("tool")
        params = a.get("params")
        if isinstance(tool, str) and isinstance(params, dict):
            out.append({"tool": tool, "params": params})
    return out
