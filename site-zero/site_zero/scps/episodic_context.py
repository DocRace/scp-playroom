"""Episodic (Chroma) text injected per SCP tick — bias helpers for rule-based behavior."""

from __future__ import annotations

import json
from typing import Any

from site_zero.world_state import WorldStateStore


def build_scp_recall_query(store: WorldStateStore, scp_id: str, tick: int) -> str:
    """Compact state snapshot for embedding search (same collection as remember writes)."""
    ent = store.get_entity(scp_id) or {}
    last = (store.get_meta().get("last_status") or {}).get(scp_id, "")
    snap: dict[str, Any] = {
        "tick": tick,
        "entity_id": scp_id,
        "location": ent.get("location"),
        "state_variables": ent.get("state_variables"),
        "prior_log": str(last)[:400],
    }
    return f"{scp_id} containment tick {tick}\n" + json.dumps(snap, default=str)[:3400]


def episodic_bias(store: WorldStateStore, salt: str, *, amp: float = 0.1) -> float:
    """
    Deterministic offset in [-amp, +amp] from the active episodic block (RAG summary).
    Used to nudge probabilities / step sizes without an extra LLM call.
    """
    block = str(store.get_meta().get("active_episodic", "") or "").strip()
    if not block:
        return 0.0
    h = hash((salt, block[:1600]))
    u = (h % 10001) / 10000.0
    return (u - 0.5) * 2.0 * amp


def episodic_suffix(store: WorldStateStore, maxlen: int = 56) -> str:
    """Short tail for log lines (debug / transparency)."""
    block = str(store.get_meta().get("active_episodic", "") or "").replace("\n", " ").strip()
    if not block:
        return ""
    tail = block[-maxlen:]
    return f" | rag={tail!r}"
