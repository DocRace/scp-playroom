"""Render Redis-style entity blobs into Markdown for agents (Jinja2)."""

from __future__ import annotations

from typing import Any

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from site_zero.perception_pov import pov_snapshot_for_entity
from site_zero.world_state import WorldStateStore

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_scp173_context(
    entities: dict[str, dict[str, Any]],
    tick: int,
    rooms: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Legacy site-wide containment summary (sim / tools). Prefer `render_entity_pov_context` for agents."""
    tpl = _env.get_template("scp173_perception.md.j2")
    return tpl.render(entities=entities, tick=tick, rooms=rooms or {})


def render_entity_pov_context(store: WorldStateStore, viewer_id: str, tick: int) -> str:
    """Markdown perception for one entity: same-room actors + local rooms only."""
    snap = pov_snapshot_for_entity(store, viewer_id, tick=tick)
    ent = snap.get("self") or {}
    loc = ent.get("location") or {}
    tpl = _env.get_template("entity_pov.md.j2")
    return tpl.render(
        viewer_id=viewer_id,
        tick=tick,
        self_room=str(loc.get("room", "?")),
        self_x=float(loc.get("x", 0) or 0),
        self_y=float(loc.get("y", 0) or 0),
        self_kind=str(ent.get("kind", "") or ""),
        others=snap.get("others_in_room") or {},
        rooms=snap.get("rooms_known") or {},
        noise=snap.get("noise_db_nearby") or {},
        neighbor_ids=list(snap.get("neighbor_room_ids") or []),
    )
