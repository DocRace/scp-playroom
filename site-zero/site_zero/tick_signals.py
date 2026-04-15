"""Expose tick progress to the GUI (which agent is currently stepping)."""

from __future__ import annotations

from site_zero.world_state import WorldStateStore


def set_tick_active_agent(store: WorldStateStore, agent_id: str | None) -> None:
    """Set ``meta['tick_active_agent']`` so the map can highlight the running agent (cleared when ``None``)."""
    meta = store.get_meta()
    if agent_id:
        meta["tick_active_agent"] = str(agent_id)
    else:
        meta.pop("tick_active_agent", None)
    store.set_meta(meta)
