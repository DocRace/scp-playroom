"""Per-agent episodic memory: Chroma persistent vector DB + Ollama embeddings (RAG-style recall)."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
import httpx

from site_zero.ollama_client import ollama_embed
from site_zero.settings import AppSettings


def format_memory_prompt_block(lines: list[str]) -> str:
    if not lines:
        return ""
    body = "\n".join(f"- {s}" for s in lines if s.strip())
    return f"### Episodic memory (retrieved, prior ticks)\n{body}\n"


def events_to_snippet(rows: list[dict[str, Any]], max_len: int = 600) -> str:
    parts: list[str] = []
    for r in rows:
        m = r.get("msg")
        if isinstance(m, str) and m.strip():
            parts.append(m.strip())
    text = " | ".join(parts)
    return text[:max_len]


class VectorAgentMemory:
    """
    One Chroma collection per agent_id (sanitized name `m_{agent_id}`).

    Used for: each D-class id, SCP-079, SCP-173, and every roster SCP tick (049, 096, …)
    so episodic traces stay isolated per entity. Recall is wired for LLM agents only;
    roster SCPs still accumulate writes for future use or tooling.
    """

    def __init__(self, settings: AppSettings) -> None:
        self._app = settings
        self._m = settings.memory
        path = Path(self._m.chroma_path)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _collection(self, agent_id: str):
        safe = "".join(c if c.isalnum() else "_" for c in agent_id)
        name = f"m_{safe}"[:200]
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    async def recall_lines(
        self,
        http: httpx.AsyncClient,
        agent_id: str,
        query_text: str,
    ) -> list[str]:
        q = (query_text or "").strip()
        if not q:
            return []
        try:
            emb = await ollama_embed(
                http,
                self._app.ollama.base_url,
                self._m.embedding_model,
                q[:8000],
                timeout=60.0,
            )
        except Exception:
            return []

        col = self._collection(agent_id)

        def _count() -> int:
            return int(col.count())

        try:
            n = await asyncio.to_thread(_count)
        except Exception:
            return []
        if n <= 0:
            return []

        k = max(1, min(self._m.recall_top_k, n))

        def _query():
            return col.query(query_embeddings=[emb], n_results=k, include=["documents"])

        try:
            res = await asyncio.to_thread(_query)
        except Exception:
            return []
        docs = res.get("documents") or []
        if not docs or not isinstance(docs[0], list):
            return []
        out: list[str] = []
        for d in docs[0]:
            if isinstance(d, str) and d.strip():
                out.append(d.strip())
        return out[: self._m.recall_top_k]

    async def remember(
        self,
        http: httpx.AsyncClient,
        agent_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        doc = (text or "").strip()
        if not doc:
            return
        try:
            emb = await ollama_embed(
                http,
                self._app.ollama.base_url,
                self._m.embedding_model,
                doc[:8000],
                timeout=60.0,
            )
        except Exception:
            return

        flat: dict[str, str | int | float | bool] = {"agent": agent_id}
        for key, val in metadata.items():
            if isinstance(val, (str, int, float, bool)):
                flat[key] = val
            else:
                flat[key] = str(val)[:500]

        mid = str(uuid.uuid4())
        col = self._collection(agent_id)

        def _add() -> None:
            col.add(
                ids=[mid],
                documents=[doc[:4000]],
                embeddings=[emb],
                metadatas=[flat],
            )

        try:
            await asyncio.to_thread(_add)
        except Exception:
            return
