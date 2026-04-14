"""
MCP-style tool surface: pure functions mutating world state.
These mirror future MCP tool names (check_light, move_to, attack, ...).
"""

from __future__ import annotations

from typing import Any, Callable

from site_zero.world_state import WorldStateStore


ToolFn = Callable[[WorldStateStore, dict[str, Any], dict[str, Any]], dict[str, Any]]


def move_entity(
    store: WorldStateStore,
    ctx: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """params: entity_id, room, x, y"""
    eid = params["entity_id"]
    ent = store.get_entity(eid)
    if not ent:
        return {"ok": False, "error": "unknown_entity"}
    loc = ent.setdefault("location", {})
    loc["room"] = params.get("room", loc.get("room"))
    loc["x"] = float(params["x"])
    loc["y"] = float(params["y"])
    store.set_entity(eid, ent)
    return {"ok": True, "entity_id": eid}


def set_observable(
    store: WorldStateStore,
    ctx: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    eid = params["entity_id"]
    ent = store.get_entity(eid)
    if not ent:
        return {"ok": False, "error": "unknown_entity"}
    ent["observable"] = bool(params.get("value", False))
    store.set_entity(eid, ent)
    return {"ok": True}


def set_room_light(
    store: WorldStateStore,
    ctx: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    room_id = params["room_id"]
    level = max(0.0, min(1.0, float(params["light_level"])))
    store.update_room(room_id, {"light_level": level})
    return {"ok": True, "room_id": room_id, "light_level": level}


def set_room_lock(
    store: WorldStateStore,
    ctx: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    room_id = params["room_id"]
    locked = bool(params["is_locked"])
    store.update_room(room_id, {"is_locked": locked})
    return {"ok": True, "room_id": room_id, "is_locked": locked}


def register_default_tools() -> dict[str, ToolFn]:
    return {
        "move_to": move_entity,
        "set_observable": set_observable,
        "set_room_light": set_room_light,
        "set_room_lock": set_room_lock,
    }


def register_phase2_tools() -> dict[str, ToolFn]:
    """MCP-style tools including site control (Phase 2)."""
    return register_default_tools()


def call_tool(
    name: str,
    store: WorldStateStore,
    ctx: dict[str, Any],
    params: dict[str, Any],
    registry: dict[str, ToolFn] | None = None,
) -> dict[str, Any]:
    reg = registry or register_phase2_tools()
    fn = reg.get(name)
    if not fn:
        return {"ok": False, "error": f"unknown_tool:{name}"}
    return fn(store, ctx, params)
