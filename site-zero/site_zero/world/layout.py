"""Site-Zero expanded topology — hub-and-spoke containment complex (fiction)."""

from __future__ import annotations

from typing import Any


def _link(g: dict[str, dict[str, Any]], a: str, b: str, loss: float = 18.0) -> None:
    ga = g.setdefault(a, {"sound_loss_db": loss, "neighbors": []})
    gb = g.setdefault(b, {"sound_loss_db": loss, "neighbors": []})
    if b not in ga["neighbors"]:
        ga["neighbors"].append(b)
    if a not in gb["neighbors"]:
        gb["neighbors"].append(a)


def build_full_site_graph() -> dict[str, dict[str, Any]]:
    """Acoustic graph: hub + wings + specialty vaults."""
    g: dict[str, dict[str, Any]] = {}
    hub = "site-hub"
    satellites = [
        ("d-holding", 12.0),
        ("con-173", 20.0),
        ("con-049", 20.0),
        ("con-096", 22.0),
        ("con-106", 22.0),
        ("con-682", 24.0),
        ("tech-914", 16.0),
        ("med-999", 14.0),
        ("core-079", 14.0),
        ("arc-055", 18.0),
        ("vid-1981", 18.0),
        ("bun-2000", 20.0),
        ("abyss-087", 21.0),
        ("mirror-093", 19.0),
        ("lake-2316", 20.0),
        ("maze-3008", 17.0),
        ("vault-2317", 23.0),
        ("rift-2935", 23.0),
        ("wild-1000", 19.0),
        ("null-2521", 25.0),
        ("site13-1730", 21.0),
        ("j-wing", 15.0),
    ]
    for room, loss in satellites:
        _link(g, hub, room, loss)
    _link(g, "tech-914", "core-079", 10.0)
    _link(g, "med-999", "tech-914", 12.0)
    _link(g, "con-173", "con-049", 14.0)
    _link(g, "con-096", "con-106", 14.0)
    _link(g, "con-106", "con-682", 16.0)
    _link(g, "arc-055", "vid-1981", 12.0)
    _link(g, "abyss-087", "mirror-093", 14.0)
    _link(g, "vault-2317", "rift-2935", 12.0)
    return g


def default_rooms_for_graph(graph: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rid in graph.keys():
        base_light = 0.62
        if "abyss" in rid or "vault" in rid or "null" in rid or "rift" in rid:
            base_light = 0.38
        if "maze" in rid:
            base_light = 0.48
        if "lake" in rid:
            base_light = 0.52
        out[rid] = {
            "is_locked": False,
            "light_level": base_light,
            "tags": _room_tags(rid),
        }
    return out


def _room_tags(rid: str) -> list[str]:
    if "abyss" in rid:
        return ["descent", "fear_zone"]
    if "lake" in rid:
        return ["cognitohazard", "water"]
    if "maze" in rid:
        return ["retail", "liminal"]
    if "mirror" in rid:
        return ["portal", "reflection"]
    if "vault" in rid or "rift" in rid:
        return ["ritual", "sealed"]
    if "j-wing" in rid:
        return ["comedic", "memetic_slack"]
    if "null" in rid:
        return ["anti-information"]
    if "wild" in rid:
        return ["perimeter", "forest"]
    if "site13" in rid:
        return ["cross_reality", "ruins"]
    return ["standard"]


# Primary export for simulation / noise / physics
SITE_ROOM_GRAPH: dict[str, dict[str, Any]] = build_full_site_graph()
SITE_DEFAULT_ROOMS: dict[str, dict[str, Any]] = default_rooms_for_graph(SITE_ROOM_GRAPH)

# Minimal sandbox (legacy): 173 cell + corridor + server core (SCP-079)
MINIMAL_ROOM_GRAPH: dict[str, dict[str, Any]] = {
    "containment-173": {"sound_loss_db": 22.0, "neighbors": ["corridor-east-a"]},
    "corridor-east-a": {"sound_loss_db": 15.0, "neighbors": ["containment-173", "server-core"]},
    "server-core": {"sound_loss_db": 18.0, "neighbors": ["corridor-east-a"]},
}
MINIMAL_DEFAULT_ROOMS: dict[str, dict[str, Any]] = {
    "containment-173": {"is_locked": False, "light_level": 0.55, "tags": ["standard"]},
    "corridor-east-a": {"is_locked": False, "light_level": 0.45, "tags": ["standard"]},
    "server-core": {"is_locked": False, "light_level": 0.4, "tags": ["standard"]},
}


def room_graph_for_meta(meta: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Active acoustic graph: full site unless meta requests minimal preset."""
    if not meta:
        return SITE_ROOM_GRAPH
    preset = str(meta.get("site_preset", "full")).lower().strip()
    if preset == "minimal":
        return MINIMAL_ROOM_GRAPH
    return SITE_ROOM_GRAPH
