"""SCP-173 — physics + optional LLM policy per tick."""

from __future__ import annotations

import math
from typing import Any

import httpx

from site_zero.ollama_client import ollama_chat_json
from site_zero.physics import nearest_living_human, propagate_noise, scp173_is_observed, step_toward
from site_zero.world.layout import room_graph_for_meta
from site_zero.settings import AppSettings
from site_zero.world_state import WorldStateStore


def load_all_entities(store: WorldStateStore) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for eid in store.list_entity_ids():
        e = store.get_entity(eid)
        if e:
            out[eid] = e
    return out


def _execute_scp173_motion(
    store: WorldStateStore,
    entities: dict[str, dict[str, Any]],
    rooms: dict[str, dict[str, Any]],
    *,
    scp_id: str = "SCP-173",
    move_step_m: float = 0.85,
    noise_move_db: float = 38.0,
) -> list[dict[str, Any]]:
    """Move one step toward nearest human when unobserved; snap if in range."""
    observed = scp173_is_observed(entities, rooms, scp_id)
    scp = entities.get(scp_id)
    if not scp:
        return [{"level": "error", "msg": "SCP-173 missing from world"}]

    scp["observable"] = observed
    store.set_entity(scp_id, scp)

    events: list[dict[str, Any]] = [
        {
            "level": "info",
            "msg": f"SCP-173 observable={observed}",
            "scp_id": scp_id,
        }
    ]

    if observed:
        events.append({"level": "warn", "msg": "SCP-173 motion frozen (line-of-sight)"})
        return events

    target = nearest_living_human(entities, scp_id, same_room_only=True)
    if not target:
        events.append({"level": "info", "msg": "No living targets in room"})
        return events

    t_ent = entities[target]
    ox = float(scp["location"]["x"])
    oy = float(scp["location"]["y"])
    tx = float(t_ent["location"]["x"])
    ty = float(t_ent["location"]["y"])
    nx, ny = step_toward(ox, oy, tx, ty, move_step_m)

    scp["location"]["x"] = nx
    scp["location"]["y"] = ny
    store.set_entity(scp_id, scp)

    room = scp["location"]["room"]
    dist = math.hypot(tx - nx, ty - ny)
    prox = float(scp.get("state_variables", {}).get("proximity_threshold_m", 0.5))
    if dist <= prox:
        t_ent["alive"] = False
        store.set_entity(target, t_ent)
        events.append({"level": "critical", "msg": f"CONTAINMENT BREACH — {target} neutralized"})
        store.publish(
            "site_zero:broadcast",
            {"type": "fatality", "victim": target, "agent": scp_id},
        )
        return events

    noise_map = propagate_noise(room, noise_move_db, room_graph_for_meta(store.get_meta()), rooms)
    events.append(
        {
            "level": "alert",
            "msg": f"SCP-173 displacement toward {target}; noise footprint {noise_map}",
            "noise_db_by_room": noise_map,
        }
    )

    store.publish(
        "site_zero:broadcast",
        {"type": "scp173_move", "target_hint": target, "noise": noise_map},
    )
    return events


def apply_scp173_tick(
    store: WorldStateStore,
    *,
    scp_id: str = "SCP-173",
    move_step_m: float = 0.85,
    noise_move_db: float = 38.0,
) -> list[dict[str, Any]]:
    entities = load_all_entities(store)
    rooms = store.get_rooms()
    return _execute_scp173_motion(
        store,
        entities,
        rooms,
        scp_id=scp_id,
        move_step_m=move_step_m,
        noise_move_db=noise_move_db,
    )


def _execute_snap_only_if_adjacent(
    store: WorldStateStore,
    entities: dict[str, dict[str, Any]],
    rooms: dict[str, dict[str, Any]],
    scp_id: str,
) -> list[dict[str, Any]] | None:
    """Returns events if snap applied, else None."""
    scp = entities.get(scp_id)
    if not scp:
        return None
    target = nearest_living_human(entities, scp_id, same_room_only=True)
    if not target:
        return []
    t_ent = entities[target]
    ox = float(scp["location"]["x"])
    oy = float(scp["location"]["y"])
    tx = float(t_ent["location"]["x"])
    ty = float(t_ent["location"]["y"])
    dist = math.hypot(tx - ox, ty - oy)
    prox = float(scp.get("state_variables", {}).get("proximity_threshold_m", 0.5))
    if dist > prox:
        return [{"level": "info", "msg": "SCP-173 snap refused (out of range)", "scp_id": scp_id}]
    t_ent["alive"] = False
    store.set_entity(target, t_ent)
    store.publish(
        "site_zero:broadcast",
        {"type": "fatality", "victim": target, "agent": scp_id},
    )
    return [
        {"level": "critical", "msg": f"CONTAINMENT BREACH — {target} neutralized", "scp_id": scp_id},
    ]


async def apply_scp173_tick_async(
    store: WorldStateStore,
    settings: AppSettings,
    http: httpx.AsyncClient,
    *,
    perception_md: str,
    memory_context: str = "",
    scp_id: str = "SCP-173",
    move_step_m: float = 0.85,
    noise_move_db: float = 38.0,
) -> list[dict[str, Any]]:
    entities = load_all_entities(store)
    rooms = store.get_rooms()
    observed = scp173_is_observed(entities, rooms, scp_id)

    if not settings.agents.use_llm:
        return _execute_scp173_motion(
            store,
            entities,
            rooms,
            scp_id=scp_id,
            move_step_m=move_step_m,
            noise_move_db=noise_move_db,
        )

    scp = entities.get(scp_id)
    if not scp:
        return [{"level": "error", "msg": "SCP-173 missing from world"}]

    system = (
        "You are SCP-173. Output JSON only: "
        '{"action":"wait|advance|snap","reason":"one sentence"}. '
        "Rules: you cannot advance or snap while directly observed (D-class line-of-sight). "
        "advance = move one step toward nearest living human in your room. "
        "snap = neutralize only if already within contact range; otherwise choose wait or advance. "
        "wait = no movement."
    )
    user = perception_md[:6000] + f"\n\nProtocol flag observable_this_tick={observed}\n"
    if memory_context.strip():
        user = memory_context.strip() + "\n\n" + user
    try:
        data = await ollama_chat_json(
            http,
            settings.ollama.base_url,
            settings.ollama.model,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            timeout=min(120.0, settings.ollama.timeout_seconds),
            temperature=0.2,
        )
        action = str(data.get("action", "wait")).lower().strip()
        reason = str(data.get("reason", ""))[:200]
    except Exception as exc:
        if settings.agents.fallback_to_rules:
            rows = _execute_scp173_motion(
                store,
                entities,
                rooms,
                scp_id=scp_id,
                move_step_m=move_step_m,
                noise_move_db=noise_move_db,
            )
            rows.insert(
                0,
                {"level": "warn", "msg": f"SCP-173 LLM failed, rules fallback ({exc})", "agent": scp_id},
            )
            return rows
        return [{"level": "error", "msg": f"SCP-173 LLM failed: {exc}", "agent": scp_id}]

    if action not in ("wait", "advance", "snap"):
        action = "wait"

    if observed and action in ("advance", "snap"):
        scp["observable"] = True
        store.set_entity(scp_id, scp)
        return [
            {"level": "info", "msg": f"SCP-173 LLM chose {action} but observed — forced wait ({reason})", "agent": scp_id},
            {"level": "warn", "msg": "SCP-173 motion frozen (line-of-sight)", "scp_id": scp_id},
        ]

    scp["observable"] = observed
    store.set_entity(scp_id, scp)

    if action == "wait":
        scp["observable"] = observed
        store.set_entity(scp_id, scp)
        return [
            {"level": "info", "msg": f"SCP-173 LLM wait ({reason})", "agent": scp_id},
            {"level": "info", "msg": f"SCP-173 observable={observed}", "scp_id": scp_id},
        ]

    if action == "snap":
        ents2 = load_all_entities(store)
        rooms2 = store.get_rooms()
        snap_ev = _execute_snap_only_if_adjacent(store, ents2, rooms2, scp_id)
        out = [{"level": "info", "msg": f"SCP-173 LLM snap ({reason})", "agent": scp_id}]
        out.extend(snap_ev)
        return out

    # advance
    ev = _execute_scp173_motion(
        store,
        load_all_entities(store),
        store.get_rooms(),
        scp_id=scp_id,
        move_step_m=move_step_m,
        noise_move_db=noise_move_db,
    )
    ev.insert(0, {"level": "info", "msg": f"SCP-173 LLM advance ({reason})", "agent": scp_id})
    return ev
