"""Hard physics rules: line of sight, noise attenuation (no LLM)."""

from __future__ import annotations

import math
from typing import Any


def normalize_vec(x: float, y: float) -> tuple[float, float]:
    d = math.hypot(x, y)
    if d < 1e-9:
        return (1.0, 0.0)
    return (x / d, y / d)


def effective_fov_degrees(
    base_fov_degrees: float,
    light_level: float,
) -> float:
    """
    Dark rooms narrow effective visual discrimination (simplified).
    light_level in [0, 1]; FOV scales between ~40° and base_fov.
    """
    lv = max(0.0, min(1.0, light_level))
    lo, hi = 40.0, base_fov_degrees
    return lo + (hi - lo) * (0.15 + 0.85 * lv)


def viewer_sees_target(
    viewer_xy: tuple[float, float],
    facing: tuple[float, float],
    target_xy: tuple[float, float],
    fov_degrees: float = 100.0,
) -> bool:
    """
    True if target lies inside viewer's forward cone (2D, same room).
    """
    vx, vy = target_xy[0] - viewer_xy[0], target_xy[1] - viewer_xy[1]
    dist = math.hypot(vx, vy)
    if dist < 1e-6:
        return True
    vx, vy = vx / dist, vy / dist
    fx, fy = normalize_vec(facing[0], facing[1])
    dot = max(-1.0, min(1.0, vx * fx + vy * fy))
    half = math.radians(fov_degrees / 2.0)
    return dot >= math.cos(half)


def scp173_is_observed(
    entities: dict[str, dict[str, Any]],
    rooms: dict[str, dict[str, Any]] | None = None,
    scp173_id: str = "SCP-173",
) -> bool:
    """
    SCP-173 is observed if any living D-class in the same room is looking at it.
    Room light_level narrows effective FOV (Phase 2).
    """
    stat = entities.get(scp173_id)
    if not stat:
        return True
    room = stat.get("location", {}).get("room")
    rooms = rooms or {}
    light = float(rooms.get(room, {}).get("light_level", 0.75))
    fov = effective_fov_degrees(100.0, light)
    sxy = (
        float(stat.get("location", {}).get("x", 0.0)),
        float(stat.get("location", {}).get("y", 0.0)),
    )
    for eid, e in entities.items():
        if eid == scp173_id:
            continue
        if e.get("kind") != "d_class":
            continue
        if not e.get("alive", True):
            continue
        if e.get("location", {}).get("room") != room:
            continue
        facing = e.get("facing", [1.0, 0.0])
        fxy = (float(facing[0]), float(facing[1]))
        txy = (
            float(e.get("location", {}).get("x", 0.0)),
            float(e.get("location", {}).get("y", 0.0)),
        )
        if viewer_sees_target(txy, fxy, sxy, fov_degrees=fov):
            return True
    return False


def nearest_living_human(
    entities: dict[str, dict[str, Any]],
    from_id: str,
    same_room_only: bool = True,
) -> str | None:
    origin = entities.get(from_id)
    if not origin:
        return None
    room = origin.get("location", {}).get("room")
    ox = float(origin.get("location", {}).get("x", 0.0))
    oy = float(origin.get("location", {}).get("y", 0.0))
    best: tuple[float, str] | None = None
    for eid, e in entities.items():
        if eid == from_id:
            continue
        if e.get("kind") != "d_class":
            continue
        if not e.get("alive", True):
            continue
        if same_room_only and e.get("location", {}).get("room") != room:
            continue
        hx = float(e.get("location", {}).get("x", 0.0))
        hy = float(e.get("location", {}).get("y", 0.0))
        d = math.hypot(hx - ox, hy - oy)
        if best is None or d < best[0]:
            best = (d, eid)
    return best[1] if best else None


def step_toward(
    ox: float,
    oy: float,
    tx: float,
    ty: float,
    max_step: float,
) -> tuple[float, float]:
    dx, dy = tx - ox, ty - oy
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return (ox, oy)
    if d <= max_step:
        return (tx, ty)
    s = max_step / d
    return (ox + dx * s, oy + dy * s)


def propagate_noise(
    source_room: str,
    noise_db: float,
    room_graph: dict[str, dict[str, Any]],
    rooms_state: dict[str, dict[str, Any]] | None = None,
    locked_extra_loss_db: float = 8.0,
) -> dict[str, float]:
    """
    Neighbor rooms receive attenuated noise. Locked doors add extra loss (Phase 2).
    """
    out: dict[str, float] = {source_room: noise_db}
    rooms_state = rooms_state or {}
    meta = room_graph.get(source_room, {})
    loss = float(meta.get("sound_loss_db", 18.0))
    for nb in meta.get("neighbors", []):
        level = noise_db - loss
        if rooms_state.get(nb, {}).get("is_locked"):
            level -= locked_extra_loss_db
        out[nb] = max(0.0, level)
    return out
