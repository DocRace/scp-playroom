"""Per-entity point of view: no site-wide entity dump in prompts or RAG queries."""

from __future__ import annotations

import json
from typing import Any

from site_zero.agents.scp173 import load_all_entities
from site_zero.world.layout import room_graph_for_meta
from site_zero.world_state import WorldStateStore


def pov_snapshot_for_entity(store: WorldStateStore, entity_id: str, *, tick: int) -> dict[str, Any]:
    """
    Information local to one entity: same-room others, this room + neighbor room env only.
    Does not include entities in non-adjacent rooms.
    """
    meta = store.get_meta()
    graph = room_graph_for_meta(meta)
    entities = load_all_entities(store)
    ent = entities.get(entity_id)
    if not ent:
        ent = store.get_entity(entity_id) or {}
    loc = ent.get("location") or {}
    room = loc.get("room")
    if not isinstance(room, str) or not room:
        return {
            "tick": tick,
            "entity_id": entity_id,
            "self": ent,
            "others_in_room": {},
            "rooms_known": {},
            "neighbor_room_ids": [],
            "noise_db_nearby": {},
        }

    neighbors: list[str] = list(graph.get(room, {}).get("neighbors", []))
    others_in_room = {
        k: v for k, v in entities.items() if k != entity_id and (v.get("location") or {}).get("room") == room
    }

    rooms_full = store.get_rooms()
    rooms_known: dict[str, Any] = {room: dict(rooms_full.get(room, {}))}
    for nb in neighbors:
        r = dict(rooms_full.get(nb, {}))
        rooms_known[nb] = {
            "is_locked": r.get("is_locked"),
            "light_level": r.get("light_level"),
            "tags": r.get("tags", []),
        }

    last_noise = meta.get("last_noise_by_room") or {}
    if not isinstance(last_noise, dict):
        last_noise = {}
    noise_db_nearby: dict[str, float] = {}
    for rid in [room, *neighbors]:
        try:
            noise_db_nearby[rid] = float(last_noise.get(rid, 0.0))
        except (TypeError, ValueError):
            noise_db_nearby[rid] = 0.0

    return {
        "tick": tick,
        "entity_id": entity_id,
        "self": ent,
        "others_in_room": others_in_room,
        "rooms_known": rooms_known,
        "neighbor_room_ids": neighbors,
        "noise_db_nearby": noise_db_nearby,
    }


def pov_snapshot_json_for_recall(store: WorldStateStore, entity_id: str, *, tick: int, max_len: int = 3400) -> str:
    snap = pov_snapshot_for_entity(store, entity_id, tick=tick)
    return f"{entity_id} tick {tick}\n" + json.dumps(snap, default=str)[:max_len]
