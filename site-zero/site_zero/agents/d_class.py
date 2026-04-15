"""D-class personnel — facing / stance from LLM policy (optional rules fallback)."""

from __future__ import annotations

import json
import math
from typing import Any

import httpx

from site_zero.agents.locomotion import (
    clamp_room_xy,
    d_class_autonomous_locomotion,
    neighbor_room_ids,
    transfer_entity_to_room,
)
from site_zero.agents.scp173 import load_all_entities
from site_zero.ollama_client import ollama_chat_json
from site_zero.perception_pov import pov_snapshot_for_entity
from site_zero.physics import scp173_is_observed
from site_zero.settings import AppSettings
from site_zero.world_state import WorldStateStore


def _scalar_float(val: Any, default: float) -> float:
    """LLMs sometimes return [x,y] or nested lists; coerce to a single float."""
    if val is None:
        return default
    if isinstance(val, bool):
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.strip())
        except ValueError:
            return default
    if isinstance(val, list) and val:
        return _scalar_float(val[0], default)
    return default


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
    tick: int = 0,
) -> list[dict[str, Any]]:
    ent = store.get_entity(entity_id)
    if not ent or not ent.get("alive", True):
        return []

    llm_on = settings.agents.use_llm if use_llm is None else use_llm
    if not llm_on:
        rows = _rules_turn_toward_173(store, entity_id, load_all_entities(store))
        rows.extend(d_class_autonomous_locomotion(store, entity_id, tick=tick))
        return rows

    snap = pov_snapshot_for_entity(store, entity_id, tick=tick)
    meta = store.get_meta()
    cur_room = (store.get_entity(entity_id) or {}).get("location", {}).get("room", "")
    nbs = neighbor_room_ids(meta, str(cur_room)) if isinstance(cur_room, str) else []
    nb_hint = ", ".join(nbs[:8]) if nbs else "(none)"
    system = (
        "You are a D-Class subject in a containment facility. Output JSON only. "
        "Required: facing_dx, facing_dy (look direction, normalized by us), intention (short phrase). "
        "Optional movement (use sparingly, must be plausible): "
        "step_dx, step_dy in [-1,1] shift inside the room; "
        f"exit_room: exact id of ONE adjacent room you step into, or null. "
        f"Your adjacent room ids this tick: [{nb_hint}]. "
        "Personality: higher fear -> more evasive exit_room or jittery steps; "
        "lower fear -> calmer or curious micro-movement. "
        "You only know your local POV (neighbor_room_ids in state). "
        "If SCP-173 is in your room and could move when unseen, keep it in view (facing)."
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
            temperature=0.42,
        )
        dx = _scalar_float(data.get("facing_dx", 1.0), 1.0)
        dy = _scalar_float(data.get("facing_dy", 0.0), 0.0)
        ent["facing"] = _normalize_facing(dx, dy)
        store.set_entity(entity_id, ent)
        intention = str(data.get("intention", ""))[:120]
        rows: list[dict[str, Any]] = [
            {
                "level": "info",
                "msg": f"{entity_id} LLM intent={intention!r}",
                "agent": entity_id,
            }
        ]
        ent = store.get_entity(entity_id) or ent
        skip_cross = False
        ex = data.get("exit_room")
        if isinstance(ex, str) and ex.strip():
            ex = ex.strip()
            here = str(ent.get("location", {}).get("room", ""))
            if ex in neighbor_room_ids(meta, here):
                transfer_entity_to_room(ent, ex)
                store.set_entity(entity_id, ent)
                skip_cross = True
                rows.append({"level": "info", "msg": f"{entity_id} LLM exit -> {ex}", "agent": entity_id})
        if not skip_cross:
            sdx = data.get("step_dx")
            sdy = data.get("step_dy")
            if sdx is not None and sdy is not None:
                fx = _scalar_float(sdx, 0.0)
                fy = _scalar_float(sdy, 0.0)
                loc = ent.setdefault("location", {"room": "?", "x": 3.0, "y": 3.0})
                nx, ny = clamp_room_xy(
                    float(loc.get("x", 3.0)) + fx * 0.55,
                    float(loc.get("y", 3.0)) + fy * 0.55,
                )
                loc["x"], loc["y"] = nx, ny
                store.set_entity(entity_id, ent)
        rows.extend(
            d_class_autonomous_locomotion(
                store,
                entity_id,
                tick=tick,
                skip_cross_room=skip_cross,
            )
        )
        return rows
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
            rows.extend(d_class_autonomous_locomotion(store, entity_id, tick=tick))
            return rows
        err = [{"level": "error", "msg": f"{entity_id} LLM failed: {exc}", "agent": entity_id}]
        err.extend(d_class_autonomous_locomotion(store, entity_id, tick=tick))
        return err
