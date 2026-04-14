"""D-class personnel — facing / stance from LLM policy (optional rules fallback)."""

from __future__ import annotations

import json
import math
from typing import Any

import httpx

from site_zero.agents.scp173 import load_all_entities
from site_zero.ollama_client import ollama_chat_json
from site_zero.physics import scp173_is_observed
from site_zero.settings import AppSettings
from site_zero.world_state import WorldStateStore


def _normalize_facing(dx: float, dy: float) -> list[float]:
    d = math.hypot(dx, dy)
    if d < 1e-9:
        return [1.0, 0.0]
    return [dx / d, dy / d]


def _rules_turn_toward_173(
    store: WorldStateStore,
    entity_id: str,
    entities: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Survival heuristic: face toward SCP-173 when in same room and it is unobserved."""
    ent = entities.get(entity_id)
    s173 = entities.get("SCP-173")
    if not ent or not s173 or not ent.get("alive", True):
        return []
    if ent.get("location", {}).get("room") != s173.get("location", {}).get("room"):
        return []
    rooms = store.get_rooms()
    if scp173_is_observed(entities, rooms, "SCP-173"):
        return []
    ox, oy = float(ent["location"]["x"]), float(ent["location"]["y"])
    tx, ty = float(s173["location"]["x"]), float(s173["location"]["y"])
    dx, dy = tx - ox, ty - oy
    ent["facing"] = _normalize_facing(dx, dy)
    store.set_entity(entity_id, ent)
    return [
        {
            "level": "info",
            "msg": f"{entity_id} facing adjusted (rules) toward anomaly",
            "agent": entity_id,
        }
    ]


async def apply_d_class_tick_async(
    store: WorldStateStore,
    settings: AppSettings,
    http: httpx.AsyncClient,
    *,
    entity_id: str = "D-9022",
    memory_context: str = "",
    use_llm: bool | None = None,
) -> list[dict[str, Any]]:
    ent = store.get_entity(entity_id)
    if not ent or not ent.get("alive", True):
        return []

    llm_on = settings.agents.use_llm if use_llm is None else use_llm
    if not llm_on:
        return _rules_turn_toward_173(store, entity_id, load_all_entities(store))

    entities = load_all_entities(store)
    snap = {
        "self": ent,
        "others": {k: v for k, v in entities.items() if k != entity_id},
        "rooms": store.get_rooms(),
    }
    system = (
        "You are a D-Class subject in a containment facility. Output JSON only: "
        '{"facing_dx": number, "facing_dy": number, "intention": "short phrase"}. '
        "facing_* is a direction you look toward (will be normalized). "
        "Survival: if SCP-173 is in your room and could move when unseen, prefer keeping it in view."
    )
    user = "State:\n" + json.dumps(snap, default=str)[:8000]
    if memory_context.strip():
        user = memory_context.strip() + "\n\n" + user
    try:
        data = await ollama_chat_json(
            http,
            settings.ollama.base_url,
            settings.ollama.model,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            timeout=min(90.0, settings.ollama.timeout_seconds),
            temperature=0.35,
        )
        dx = float(data.get("facing_dx", 1.0))
        dy = float(data.get("facing_dy", 0.0))
        ent["facing"] = _normalize_facing(dx, dy)
        store.set_entity(entity_id, ent)
        intention = str(data.get("intention", ""))[:120]
        return [
            {
                "level": "info",
                "msg": f"{entity_id} LLM facing intent={intention!r}",
                "agent": entity_id,
            }
        ]
    except Exception as exc:
        if settings.agents.fallback_to_rules:
            rows = _rules_turn_toward_173(store, entity_id, load_all_entities(store))
            rows.insert(
                0,
                {
                    "level": "warn",
                    "msg": f"{entity_id} LLM failed, rules fallback ({exc})",
                    "agent": entity_id,
                },
            )
            return rows
        return [{"level": "error", "msg": f"{entity_id} LLM failed: {exc}", "agent": entity_id}]
