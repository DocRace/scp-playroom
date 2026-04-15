"""In-world movement helpers — rooms graph, clamps, D-class autonomy, light SCP patrol."""

from __future__ import annotations

import random
from typing import Any

from site_zero.world.layout import room_graph_for_meta
from site_zero.world_state import WorldStateStore

# Generic bounds for local room coordinates (simulation units).
_XY_MIN = 0.45
_XY_MAX = 8.35


def clamp_room_xy(x: float, y: float) -> tuple[float, float]:
    return max(_XY_MIN, min(_XY_MAX, x)), max(_XY_MIN, min(_XY_MAX, y))


def neighbor_room_ids(meta: dict[str, Any] | None, room: str) -> list[str]:
    g = room_graph_for_meta(meta)
    return list(g.get(room, {}).get("neighbors", []))


def pick_neighbor_weighted(meta: dict[str, Any] | None, room: str, *, prefer_hub: bool) -> str | None:
    nbs = neighbor_room_ids(meta, room)
    if not nbs:
        return None
    hub = "site-hub"
    if prefer_hub and hub in nbs:
        if random.random() < 0.38:
            return hub
    return random.choice(nbs)


def nudge_xy_in_room(ent: dict[str, Any], scale: float) -> None:
    loc = ent.setdefault("location", {"room": "?", "x": 3.0, "y": 3.0})
    x = float(loc.get("x", 3.0))
    y = float(loc.get("y", 3.0))
    nx, ny = clamp_room_xy(
        x + random.uniform(-scale, scale),
        y + random.uniform(-scale, scale),
    )
    loc["x"], loc["y"] = nx, ny


def transfer_entity_to_room(ent: dict[str, Any], new_room: str) -> None:
    loc = ent.setdefault("location", {"room": new_room, "x": 3.0, "y": 3.0})
    loc["room"] = new_room
    loc["x"] = random.uniform(1.1, 6.2)
    loc["y"] = random.uniform(1.1, 6.2)


def d_class_autonomous_locomotion(
    store: WorldStateStore,
    entity_id: str,
    *,
    tick: int,
    skip_cross_room: bool = False,
) -> list[dict[str, Any]]:
    """
    Personality-driven patrol / flee using fear, cognitive_load, and local threats.
    """
    ent = store.get_entity(entity_id)
    if not ent or ent.get("kind") != "d_class" or not ent.get("alive", True):
        return []

    meta = store.get_meta()
    room = ent.get("location", {}).get("room")
    if not isinstance(room, str) or not room:
        return []

    entities = {eid: store.get_entity(eid) for eid in store.list_entity_ids()}
    entities = {k: v for k, v in entities.items() if v}

    scp_here = any(
        e.get("kind") == "scp" and e.get("location", {}).get("room") == room
        for e in entities.values()
    )

    sv = ent.setdefault("state_variables", {})
    fear = float(sv.get("fear", 0.2))
    cog = float(sv.get("cognitive_load", 0.2))
    restlessness = 0.55 * (1.0 - fear) + 0.35 * cog + 0.12 * (hash(entity_id) % 17) / 17.0

    nbs = neighbor_room_ids(meta, room)
    p_leave = 0.028 + fear * 0.16 + (0.26 if scp_here else 0.0) + restlessness * 0.045
    trait = str(ent.get("trait", "") or "")
    if trait in ("reckless", "defiant", "curious"):
        p_leave *= 1.22
    elif trait in ("docile", "numb", "clingy"):
        p_leave *= 0.78
    p_leave = max(0.0, min(0.72, p_leave))

    out: list[dict[str, Any]] = []

    if nbs and not skip_cross_room and random.random() < p_leave:
        prefer_hub = not scp_here and fear < 0.38
        target = pick_neighbor_weighted(meta, room, prefer_hub=prefer_hub)
        if target:
            tag = "flee" if scp_here else "patrol"
            transfer_entity_to_room(ent, target)
            store.set_entity(entity_id, ent)
            out.append(
                {
                    "level": "info",
                    "msg": f"{entity_id} move={tag} -> {target}",
                    "agent": entity_id,
                }
            )
            return out

    step = 0.12 + (1.0 - fear) * 0.42 + cog * 0.2
    nudge_xy_in_room(ent, scale=step)
    store.set_entity(entity_id, ent)
    if random.random() < 0.06:
        out.append({"level": "debug", "msg": f"{entity_id} drift in {room}", "agent": entity_id})
    return out


def scp_in_room_drift(store: WorldStateStore, eid: str, amp: float) -> None:
    ent = store.get_entity(eid)
    if not ent:
        return
    nudge_xy_in_room(ent, scale=amp)
    store.set_entity(eid, ent)


def scp_maybe_patrol_adjacent(
    store: WorldStateStore,
    eid: str,
    p: float,
    *,
    msg_verb: str = "patrol",
) -> list[dict[str, Any]]:
    if random.random() > p:
        return []
    ent = store.get_entity(eid)
    if not ent:
        return []
    room = ent.get("location", {}).get("room")
    if not isinstance(room, str):
        return []
    meta = store.get_meta()
    nbs = neighbor_room_ids(meta, room)
    if not nbs:
        return []
    target = random.choice(nbs)
    transfer_entity_to_room(ent, target)
    store.set_entity(eid, ent)
    return [{"level": "info", "msg": f"{eid} act={msg_verb} -> {target}", "agent": eid}]


def scp_joke_relocate(store: WorldStateStore, eid: str, p: float) -> list[dict[str, Any]]:
    if random.random() > p:
        return []
    ent = store.get_entity(eid)
    if not ent:
        return []
    rooms = store.get_rooms()
    if not rooms:
        return []
    target = random.choice(list(rooms.keys()))
    transfer_entity_to_room(ent, target)
    store.set_entity(eid, ent)
    return [{"level": "warn", "msg": f"{eid} act=slack_jump -> {target}", "agent": eid}]
