"""Dispatch rule-based SCP ticks (excluding SCP-173 when LLM path handles it last)."""

from __future__ import annotations

from typing import Any

from site_zero.scps.ticks_top20 import SCP_TICK_ORDER_EXCEPT_173, TICK_REGISTRY
from site_zero.world_state import WorldStateStore


async def dispatch_scp_ticks_except_173(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    """Run perceive→act handlers for all roster SCPs except SCP-173."""
    out: list[dict[str, Any]] = []
    for scp_id in SCP_TICK_ORDER_EXCEPT_173:
        fn = TICK_REGISTRY.get(scp_id)
        if not fn:
            continue
        if store.get_entity(scp_id) is None:
            continue
        try:
            rows = fn(store, tick)
            for ev in rows:
                ev.setdefault("agent", scp_id)
            out.extend(rows)
        except Exception as exc:
            out.append({"level": "error", "msg": f"{scp_id} tick failed: {exc}", "agent": scp_id})
    return out
