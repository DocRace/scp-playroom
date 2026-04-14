"""Site-Zero topology — floor plan + acoustic graph (fiction).

The full preset is one subterranean **research containment level** with normalized floor
coordinates (layout_xy in 0–1). Edges follow walkable adjacency (corridors / airlocks),
not a star from a single hub. The live map uses ``layout_xy``. ``sound_loss_db`` on each
node is the attenuation for noise leaving that room (one value per room in current physics).
"""

from __future__ import annotations

from typing import Any


def _link(g: dict[str, dict[str, Any]], a: str, b: str, loss: float = 18.0) -> None:
    ga = g.setdefault(a, {"sound_loss_db": loss, "neighbors": []})
    gb = g.setdefault(b, {"sound_loss_db": loss, "neighbors": []})
    if b not in ga["neighbors"]:
        ga["neighbors"].append(b)
    if a not in gb["neighbors"]:
        gb["neighbors"].append(a)


# Normalized floor coordinates (x right, y down).
# North: perimeter / D-holding; center: atrium; south: engineering; west: bio/humanoid;
# east: heavy containment + annex chain.
FULL_SITE_LAYOUT_XY: dict[str, tuple[float, float]] = {
    # North band: perimeter and intake
    "wild-1000": (0.22, 0.10),
    "site13-1730": (0.58, 0.10),
    "d-holding": (0.42, 0.20),
    "j-wing": (0.68, 0.22),
    # Central atrium
    "site-hub": (0.50, 0.38),
    # West wing (humanoid / bio / void-adjacent)
    "null-2521": (0.08, 0.34),
    "mirror-093": (0.14, 0.40),
    "con-173": (0.28, 0.38),
    "con-049": (0.18, 0.50),
    "abyss-087": (0.10, 0.56),
    "med-999": (0.24, 0.60),
    # East wing (heavy containment + lake)
    "lake-2316": (0.80, 0.28),
    "con-096": (0.72, 0.38),
    "con-106": (0.82, 0.48),
    "con-682": (0.88, 0.56),
    # South spine: tech, records, narrative bunker
    "tech-914": (0.50, 0.56),
    "arc-055": (0.36, 0.62),
    "core-079": (0.62, 0.64),
    "vid-1981": (0.46, 0.74),
    "bun-2000": (0.54, 0.82),
    # Far east annex chain (retail, ritual, rift)
    "maze-3008": (0.78, 0.70),
    "vault-2317": (0.90, 0.74),
    "rift-2935": (0.90, 0.88),
}


def build_full_site_graph() -> dict[str, dict[str, Any]]:
    """
    Walkable adjacency matching the floor plan:

    - **North**: perimeter (wild-1000) into D-holding; site13 annex off j-wing.
    - **Center**: site-hub connects N/S spine and both wings.
    - **West corridor**: 173 ↔ 049 ↔ med, with mirror/null/abyss branches.
    - **East corridor**: 096 ↔ 106 ↔ 682, lake off 096; annex chain off 682.
    - **South**: hub -> 914 -> branches to 079 core, 055, tapes/2000.
    """
    g: dict[str, dict[str, Any]] = {}

    def ln(a: str, b: str, loss: float) -> None:
        _link(g, a, b, loss)

    # Perimeter & intake
    ln("wild-1000", "d-holding", 22.0)
    ln("d-holding", "site-hub", 14.0)
    ln("site13-1730", "j-wing", 18.0)
    ln("j-wing", "site-hub", 16.0)

    # Central atrium to wings + main south corridor
    ln("site-hub", "con-173", 16.0)
    ln("site-hub", "con-096", 16.0)
    ln("site-hub", "tech-914", 14.0)

    # West wing chain & branches
    ln("con-173", "con-049", 14.0)
    ln("con-049", "med-999", 15.0)
    ln("con-049", "mirror-093", 17.0)
    ln("mirror-093", "null-2521", 24.0)
    ln("med-999", "abyss-087", 20.0)

    # East wing chain
    ln("con-096", "lake-2316", 18.0)
    ln("con-096", "con-106", 14.0)
    ln("con-106", "con-682", 16.0)

    # South engineering / archives
    ln("tech-914", "core-079", 12.0)
    ln("tech-914", "arc-055", 14.0)
    ln("tech-914", "vid-1981", 13.0)
    ln("core-079", "vid-1981", 11.0)
    ln("vid-1981", "bun-2000", 16.0)

    # East annex (single-file vault line)
    ln("con-682", "maze-3008", 19.0)
    ln("maze-3008", "vault-2317", 17.0)
    ln("vault-2317", "rift-2935", 15.0)

    for rid, xy in FULL_SITE_LAYOUT_XY.items():
        node = g.setdefault(rid, {"sound_loss_db": 18.0, "neighbors": []})
        node["layout_xy"] = [float(xy[0]), float(xy[1])]

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
        if rid == "site-hub":
            base_light = 0.72
        if rid in ("core-079", "tech-914", "arc-055"):
            base_light = 0.55
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
        return ["anti_information"]
    if "wild" in rid:
        return ["perimeter", "forest"]
    if "site13" in rid:
        return ["cross_reality", "ruins"]
    if rid == "site-hub":
        return ["atrium", "checkpoint"]
    if rid == "d-holding":
        return ["intake", "personnel"]
    if "core-079" in rid:
        return ["server", "ai_housing"]
    return ["standard"]


# Primary export for simulation / noise / physics
SITE_ROOM_GRAPH: dict[str, dict[str, Any]] = build_full_site_graph()
SITE_DEFAULT_ROOMS: dict[str, dict[str, Any]] = default_rooms_for_graph(SITE_ROOM_GRAPH)

# Minimal sandbox (legacy): 173 cell + corridor + server core (SCP-079)
MINIMAL_ROOM_GRAPH: dict[str, dict[str, Any]] = {
    "containment-173": {
        "sound_loss_db": 22.0,
        "neighbors": ["corridor-east-a"],
        "layout_xy": [0.22, 0.50],
    },
    "corridor-east-a": {
        "sound_loss_db": 15.0,
        "neighbors": ["containment-173", "server-core"],
        "layout_xy": [0.52, 0.50],
    },
    "server-core": {
        "sound_loss_db": 18.0,
        "neighbors": ["corridor-east-a"],
        "layout_xy": [0.82, 0.50],
    },
}

MINIMAL_DEFAULT_ROOMS: dict[str, dict[str, Any]] = {
    "containment-173": {"is_locked": False, "light_level": 0.55, "tags": ["standard"]},
    "corridor-east-a": {"is_locked": False, "light_level": 0.45, "tags": ["corridor"]},
    "server-core": {"is_locked": False, "light_level": 0.4, "tags": ["server"]},
}


def room_graph_for_meta(meta: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Active acoustic graph: full site unless meta requests minimal preset."""
    if not meta:
        return SITE_ROOM_GRAPH
    preset = str(meta.get("site_preset", "full")).lower().strip()
    if preset == "minimal":
        return MINIMAL_ROOM_GRAPH
    return SITE_ROOM_GRAPH
