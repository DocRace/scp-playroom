"""Dispatch rule-based SCP ticks (excluding SCP-173 when LLM path handles it last)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from site_zero.memory.vector_memory import VectorAgentMemory, format_memory_prompt_block
from site_zero.scps.episodic_context import build_scp_recall_query
from site_zero.scps.ticks_top20 import SCP_TICK_ORDER_EXCEPT_173, TICK_REGISTRY
from site_zero.world_state import WorldStateStore


async def dispatch_scp_ticks_except_173(
    store: WorldStateStore,
    tick: int,
    *,
    memory: VectorAgentMemory | None = None,
    http: httpx.AsyncClient | None = None,
    roster_recall: bool = False,
    roster_recall_timeout: float = 45.0,
) -> list[dict[str, Any]]:
    """Run perceive→act handlers; optional RAG recall into meta['active_episodic'] per SCP."""
    out: list[dict[str, Any]] = []
    for scp_id in SCP_TICK_ORDER_EXCEPT_173:
        fn = TICK_REGISTRY.get(scp_id)
        if not fn:
            continue
        if store.get_entity(scp_id) is None:
            continue
        injected = False
        try:
            if roster_recall and memory is not None and http is not None:
                q = build_scp_recall_query(store, scp_id, tick)
                try:
                    lines = await asyncio.wait_for(
                        memory.recall_lines(http, scp_id, q),
                        timeout=max(5.0, roster_recall_timeout),
                    )
                except TimeoutError:
                    lines = []
                block = format_memory_prompt_block(lines)
                meta = store.get_meta()
                if block.strip():
                    meta["active_episodic"] = block
                else:
                    meta.pop("active_episodic", None)
                store.set_meta(meta)
                injected = True
            rows = fn(store, tick)
            for ev in rows:
                ev.setdefault("agent", scp_id)
            out.extend(rows)
        except Exception as exc:
            out.append({"level": "error", "msg": f"{scp_id} tick failed: {exc}", "agent": scp_id})
        finally:
            if injected:
                meta = store.get_meta()
                meta.pop("active_episodic", None)
                store.set_meta(meta)
    return out
