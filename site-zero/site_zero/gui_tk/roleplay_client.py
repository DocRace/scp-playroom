"""Synchronous Ollama /api/chat for GUI roleplay (no JSON mode)."""

from __future__ import annotations

from typing import Any

import httpx


def ollama_roleplay_chat(
    base_url: str,
    model: str,
    system: str,
    messages: list[dict[str, str]],
    *,
    timeout: float = 120.0,
    temperature: float = 0.62,
) -> str:
    """Plain chat completion; ``messages`` are user/assistant turns only (no system)."""
    url = f"{base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": False,
        "options": {"temperature": temperature},
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        return str(data.get("message", {}).get("content", "")).strip()
