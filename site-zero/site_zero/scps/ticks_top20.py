"""
Rule-based perceive→think→act for top-community SCP roster.
Fiction: simplified mechanics for multi-agent lab simulation (not canon-accurate).
"""

from __future__ import annotations

import math
import random
from typing import Any

from site_zero.agents.scp173 import load_all_entities
from site_zero.physics import nearest_living_human, propagate_noise, step_toward
from site_zero.world.layout import room_graph_for_meta
from site_zero.world_state import WorldStateStore


def _rooms(store: WorldStateStore) -> dict[str, dict[str, Any]]:
    return store.get_rooms()


def _publish(store: WorldStateStore, payload: dict[str, Any]) -> None:
    store.publish("site_zero:broadcast", payload)


def tick_scp_049(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    eid = "SCP-049"
    entities = load_all_entities(store)
    ent = entities.get(eid)
    if not ent:
        return []
    room = ent["location"]["room"]
    target = nearest_living_human(entities, eid, same_room_only=True)
    events: list[dict[str, Any]] = [
        {"level": "info", "msg": f"{eid} perceive=plague_scan think=cure_compulsion", "agent": eid}
    ]
    if not target:
        return events
    ox, oy = float(ent["location"]["x"]), float(ent["location"]["y"])
    tx, ty = float(entities[target]["location"]["x"]), float(entities[target]["location"]["y"])
    if math.hypot(tx - ox, ty - oy) <= 0.65:
        v = entities[target].setdefault("state_variables", {})
        v["infected"] = True
        store.set_entity(target, entities[target])
        events.append({"level": "alert", "msg": f"{eid} act=cure_touch {target}", "agent": eid})
        return events
    nx, ny = step_toward(ox, oy, tx, ty, 0.55)
    ent["location"]["x"], ent["location"]["y"] = nx, ny
    store.set_entity(eid, ent)
    nm = propagate_noise(room, 32.0, room_graph_for_meta(store.get_meta()), _rooms(store))
    events.append({"level": "warn", "msg": f"{eid} act=pursue noise={nm}", "noise_db_by_room": nm, "agent": eid})
    return events


def tick_scp_096(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    eid = "SCP-096"
    entities = load_all_entities(store)
    ent = entities.get(eid)
    if not ent:
        return []
    sv = ent.setdefault("state_variables", {})
    room = ent["location"]["room"]
    if not sv.get("enraged"):
        for oid, o in entities.items():
            if o.get("kind") != "d_class" or not o.get("alive"):
                continue
            if o.get("location", {}).get("room") == room and random.random() < 0.08:
                sv["face_compromised"] = True
                sv["enraged"] = True
                sv["rage_target"] = oid
                break
    events = [{"level": "info", "msg": f"{eid} perceive=face_rule enraged={sv.get('enraged')}", "agent": eid}]
    if not sv.get("enraged"):
        store.set_entity(eid, ent)
        return events
    tid = sv.get("rage_target")
    tgt = entities.get(tid) if tid else None
    if not tgt or not tgt.get("alive"):
        sv["enraged"] = False
        store.set_entity(eid, ent)
        return events
    ox, oy = float(ent["location"]["x"]), float(ent["location"]["y"])
    tx, ty = float(tgt["location"]["x"]), float(tgt["location"]["y"])
    if tgt["location"]["room"] != room:
        sv["enraged"] = False
        store.set_entity(eid, ent)
        events.append({"level": "info", "msg": f"{eid} think=target_lost calm", "agent": eid})
        return events
    nx, ny = step_toward(ox, oy, tx, ty, 1.1)
    ent["location"]["x"], ent["location"]["y"] = nx, ny
    store.set_entity(eid, ent)
    if math.hypot(tx - nx, ty - ny) < 0.45:
        tgt["alive"] = False
        store.set_entity(tid, tgt)
        sv["enraged"] = False
        events.append({"level": "critical", "msg": f"{eid} act=terminate {tid}", "agent": eid})
        _publish(store, {"type": "fatality", "victim": tid, "agent": eid})
        store.set_entity(eid, ent)
        return events
    nm = propagate_noise(room, 44.0, room_graph_for_meta(store.get_meta()), _rooms(store))
    events.append({"level": "alert", "msg": f"{eid} act=sprint", "noise_db_by_room": nm, "agent": eid})
    store.set_entity(eid, ent)
    return events


def tick_scp_682(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    eid = "SCP-682"
    entities = load_all_entities(store)
    ent = entities.get(eid)
    if not ent:
        return []
    room = ent["location"]["room"]
    target = nearest_living_human(entities, eid, same_room_only=True)
    events: list[dict[str, Any]] = [{"level": "info", "msg": f"{eid} perceive=life_map hatred=high", "agent": eid}]
    if not target:
        return events
    ox, oy = float(ent["location"]["x"]), float(ent["location"]["y"])
    tx, ty = float(entities[target]["location"]["x"]), float(entities[target]["location"]["y"])
    nx, ny = step_toward(ox, oy, tx, ty, 0.45)
    ent["location"]["x"], ent["location"]["y"] = nx, ny
    store.set_entity(eid, ent)
    nm = propagate_noise(room, 48.0, room_graph_for_meta(store.get_meta()), _rooms(store))
    events.append({"level": "alert", "msg": f"{eid} act=lunge", "noise_db_by_room": nm, "agent": eid})
    return events


def tick_scp_106(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    eid = "SCP-106"
    entities = load_all_entities(store)
    ent = entities.get(eid)
    if not ent:
        return []
    if tick % 4 != 0:
        return [{"level": "debug", "msg": f"{eid} idle_phase", "agent": eid}]
    room = ent["location"]["room"]
    pool = [k for k, v in entities.items() if v.get("kind") == "d_class" and v.get("alive")]
    if not pool:
        return [{"level": "info", "msg": f"{eid} perceive=none", "agent": eid}]
    victim = random.choice(pool)
    vr = entities[victim]["location"]["room"]
    ent["location"]["room"] = vr
    ent["location"]["x"] = float(entities[victim]["location"]["x"]) + 0.3
    ent["location"]["y"] = float(entities[victim]["location"]["y"])
    store.set_entity(eid, ent)
    nm = propagate_noise(vr, 36.0, room_graph_for_meta(store.get_meta()), _rooms(store))
    return [
        {"level": "alert", "msg": f"{eid} act=phase_near {victim}", "noise_db_by_room": nm, "agent": eid},
    ]


def tick_scp_999(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    eid = "SCP-999"
    entities = load_all_entities(store)
    ent = entities.get(eid)
    if not ent:
        return []
    room = ent["location"]["room"]
    best = None
    best_f = -1.0
    for oid, o in entities.items():
        if o.get("kind") != "d_class" or not o.get("alive"):
            continue
        if o.get("location", {}).get("room") != room:
            continue
        f = float(o.get("state_variables", {}).get("fear", 0.0))
        if f > best_f:
            best_f, best = f, oid
    events: list[dict[str, Any]] = [{"level": "info", "msg": f"{eid} perceive=distress", "agent": eid}]
    if not best:
        return events
    ox, oy = float(ent["location"]["x"]), float(ent["location"]["y"])
    tx, ty = float(entities[best]["location"]["x"]), float(entities[best]["location"]["y"])
    nx, ny = step_toward(ox, oy, tx, ty, 0.4)
    ent["location"]["x"], ent["location"]["y"] = nx, ny
    store.set_entity(eid, ent)
    sv = entities[best].setdefault("state_variables", {})
    sv["fear"] = max(0.0, float(sv.get("fear", 0)) - 0.12)
    store.set_entity(best, entities[best])
    events.append({"level": "info", "msg": f"{eid} act=calm {best}", "agent": eid})
    return events


def tick_scp_055(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    eid = "SCP-055"
    rooms = _rooms(store)
    if not rooms:
        return []
    rid = random.choice(list(rooms.keys()))
    cur = float(rooms[rid].get("light_level", 0.5))
    store.update_room(rid, {"light_level": max(0.05, min(1.0, cur + random.uniform(-0.08, 0.08)))})
    return [{"level": "info", "msg": f"{eid} act=subtle_light_shift {rid}", "agent": eid}]


def tick_scp_087(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    entities = load_all_entities(store)
    for oid, o in entities.items():
        if o.get("kind") != "d_class" or not o.get("alive"):
            continue
        if o.get("location", {}).get("room") == "abyss-087":
            sv = o.setdefault("state_variables", {})
            sv["fear"] = min(1.0, float(sv.get("fear", 0)) + 0.06)
            store.set_entity(oid, o)
    return [{"level": "warn", "msg": "SCP-087 act=descent_pressure (entities in abyss)", "agent": "SCP-087"}]


def tick_scp_093(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    if random.random() > 0.12:
        return [{"level": "debug", "msg": "SCP-093 idle", "agent": "SCP-093"}]
    entities = load_all_entities(store)
    ds = [k for k, v in entities.items() if v.get("kind") == "d_class" and v.get("alive")]
    if len(ds) < 2:
        return [{"level": "info", "msg": "SCP-093 perceive=insufficient_pairs", "agent": "SCP-093"}]
    a, b = random.sample(ds, 2)
    la, lb = entities[a]["location"], entities[b]["location"]
    entities[a]["location"], entities[b]["location"] = dict(lb), dict(la)
    store.set_entity(a, entities[a])
    store.set_entity(b, entities[b])
    return [{"level": "alert", "msg": f"SCP-093 act=mirror_swap {a}<->{b}", "agent": "SCP-093"}]


def tick_scp_914(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    entities = load_all_entities(store)
    pool = [k for k, v in entities.items() if v.get("kind") in ("d_class", "scp") and k != "SCP-914"]
    if not pool:
        return []
    tid = random.choice(pool)
    o = entities[tid]
    sv = o.setdefault("state_variables", {})
    if random.random() < 0.5:
        sv["cognitive_load"] = min(1.0, float(sv.get("cognitive_load", 0)) + 0.05)
        mode = "fine"
    else:
        sv["cognitive_load"] = max(0.0, float(sv.get("cognitive_load", 0)) - 0.07)
        mode = "coarse"
    store.set_entity(tid, o)
    return [{"level": "info", "msg": f"SCP-914 act=refine_{mode} {tid}", "agent": "SCP-914"}]


def tick_scp_2316(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    entities = load_all_entities(store)
    n = 0
    for oid, o in entities.items():
        if o.get("kind") != "d_class" or not o.get("alive"):
            continue
        if o.get("location", {}).get("room") == "lake-2316":
            sv = o.setdefault("state_variables", {})
            sv["cognitive_load"] = min(1.0, float(sv.get("cognitive_load", 0)) + 0.09)
            sv["fear"] = min(1.0, float(sv.get("fear", 0)) + 0.05)
            store.set_entity(oid, o)
            n += 1
    return [{"level": "warn", "msg": f"SCP-2316 act=cognito_lake affected={n}", "agent": "SCP-2316"}]


def tick_scp_2317(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    meta = store.get_meta()
    c = float(meta.get("chain_strain", 0.0)) + 0.003
    meta["chain_strain"] = c
    store.set_meta(meta)
    if c > 0.35:
        _publish(store, {"type": "2317_strain", "level": c})
    return [{"level": "warn", "msg": f"SCP-2317 act=dread_pulse strain={c:.3f}", "agent": "SCP-2317"}]


def tick_scp_2000(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    if tick % 17 != 0:
        return [{"level": "debug", "msg": "SCP-2000 watch", "agent": "SCP-2000"}]
    meta = store.get_meta()
    meta["rebuild_armed"] = True
    store.set_meta(meta)
    return [{"level": "info", "msg": "SCP-2000 act=contingency_ping", "agent": "SCP-2000"}]


def tick_scp_1981(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    entities = load_all_entities(store)
    for oid, o in entities.items():
        if o.get("kind") != "d_class" or not o.get("alive"):
            continue
        sv = o.setdefault("state_variables", {})
        sv["fear"] = min(1.0, float(sv.get("fear", 0)) + 0.02)
        store.set_entity(oid, o)
    return [{"level": "info", "msg": "SCP-1981 act=signal_cut_whisper", "agent": "SCP-1981"}]


def tick_scp_2935(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    meta = store.get_meta()
    leak = float(meta.get("dead_universe_leak", 0.0)) + 0.002
    meta["dead_universe_leak"] = leak
    store.set_meta(meta)
    return [{"level": "warn", "msg": f"SCP-2935 act=entropy_check leak={leak:.4f}", "agent": "SCP-2935"}]


def tick_scp_2521(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    if random.random() > 0.07:
        return [{"level": "debug", "msg": "SCP-2521 silent", "agent": "SCP-2521"}]
    entities = load_all_entities(store)
    ds = [k for k, v in entities.items() if v.get("kind") == "d_class" and v.get("alive")]
    if not ds:
        return []
    v = random.choice(ds)
    ent = entities[v]
    ent["location"] = {"room": "null-2521", "x": 0.0, "y": 0.0}
    sv = ent.setdefault("state_variables", {})
    sv["abducted"] = True
    store.set_entity(v, ent)
    return [{"level": "critical", "msg": f"SCP-2521 act=abduct {v}", "agent": "SCP-2521"}]


def tick_scp_3008(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    store.update_room("maze-3008", {"light_level": max(0.12, float(_rooms(store).get("maze-3008", {}).get("light_level", 0.5)) - 0.03)})
    return [{"level": "info", "msg": "SCP-3008 act=closing_shift_dim", "agent": "SCP-3008"}]


def tick_scp_1730(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    nm = propagate_noise("site13-1730", 28.0, room_graph_for_meta(store.get_meta()), _rooms(store))
    return [{"level": "warn", "msg": "SCP-1730 act=structural_echo", "noise_db_by_room": nm, "agent": "SCP-1730"}]


def tick_scp_1000(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    return [{"level": "debug", "msg": "SCP-1000 act=observe_forest", "agent": "SCP-1000"}]


def tick_scp_j(store: WorldStateStore, tick: int) -> list[dict[str, Any]]:
    meta = store.get_meta()
    p = int(meta.get("procrastination_ticks", 0)) + 1
    meta["procrastination_ticks"] = p
    store.set_meta(meta)
    return [{"level": "info", "msg": f"SCP-____-J act=defer_counter={p}", "agent": "SCP-____-J"}]


TICK_REGISTRY: dict[str, Any] = {
    "SCP-049": tick_scp_049,
    "SCP-096": tick_scp_096,
    "SCP-682": tick_scp_682,
    "SCP-106": tick_scp_106,
    "SCP-999": tick_scp_999,
    "SCP-055": tick_scp_055,
    "SCP-087": tick_scp_087,
    "SCP-093": tick_scp_093,
    "SCP-914": tick_scp_914,
    "SCP-2316": tick_scp_2316,
    "SCP-2317": tick_scp_2317,
    "SCP-2000": tick_scp_2000,
    "SCP-1981": tick_scp_1981,
    "SCP-2935": tick_scp_2935,
    "SCP-2521": tick_scp_2521,
    "SCP-3008": tick_scp_3008,
    "SCP-1730": tick_scp_1730,
    "SCP-1000": tick_scp_1000,
    "SCP-____-J": tick_scp_j,
}

SCP_TICK_ORDER_EXCEPT_173: tuple[str, ...] = (
    "SCP-055",
    "SCP-049",
    "SCP-087",
    "SCP-093",
    "SCP-096",
    "SCP-1000",
    "SCP-106",
    "SCP-682",
    "SCP-914",
    "SCP-999",
    "SCP-1730",
    "SCP-1981",
    "SCP-2000",
    "SCP-2316",
    "SCP-2317",
    "SCP-2521",
    "SCP-2935",
    "SCP-3008",
    "SCP-____-J",
)
