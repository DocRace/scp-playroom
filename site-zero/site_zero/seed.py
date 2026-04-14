"""Initial world layout — rooms graph, entities, Phase-2 site systems."""

from __future__ import annotations

from typing import Any, Literal

from site_zero.entity_roster import full_site_entities, minimal_entities
from site_zero.world.layout import MINIMAL_DEFAULT_ROOMS, SITE_DEFAULT_ROOMS, SITE_ROOM_GRAPH
from site_zero.world_state import WorldStateStore

# Back-compat alias — full-site graph; runtime physics uses room_graph_for_meta(store.get_meta()).
ROOM_GRAPH = SITE_ROOM_GRAPH

SitePreset = Literal["full", "minimal"]


def _rooms_for_preset(site_preset: SitePreset) -> dict[str, dict[str, Any]]:
    return MINIMAL_DEFAULT_ROOMS if site_preset == "minimal" else SITE_DEFAULT_ROOMS


def _entities_for_preset(site_preset: SitePreset) -> dict[str, dict[str, Any]]:
    return minimal_entities() if site_preset == "minimal" else full_site_entities()


def default_rooms() -> dict[str, dict[str, Any]]:
    """Default room table for the active preset (full unless configured elsewhere)."""
    return _rooms_for_preset("full")


def default_entities() -> dict[str, dict[str, Any]]:
    """Default entity roster for full site (20 D-class + top-20 SCP roster + SCP-079)."""
    return _entities_for_preset("full")


def ensure_world_seed(store: WorldStateStore, *, site_preset: SitePreset = "full") -> None:
    """Idempotent seed for entities and room control state."""
    preset: SitePreset = site_preset if site_preset in ("full", "minimal") else "full"
    meta = store.get_meta()
    meta["site_preset"] = preset
    store.set_meta(meta)

    for eid, blob in _entities_for_preset(preset).items():
        if store.get_entity(eid) is None:
            store.set_entity(eid, blob)

    rooms = store.get_rooms()
    base = _rooms_for_preset(preset)
    if not rooms:
        store.replace_rooms(base)
    else:
        merged: dict[str, dict[str, Any]] = {}
        for rid, defaults in base.items():
            cur = rooms.get(rid, {})
            merged[rid] = {**defaults, **cur}
        for rid, cur in rooms.items():
            if rid not in merged:
                merged[rid] = {**base.get(rid, {}), **cur}
        store.replace_rooms(merged)
