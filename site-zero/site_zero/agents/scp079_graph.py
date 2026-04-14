"""LangGraph state machine for SCP-079 — observe → plan → execute (site controls)."""

from __future__ import annotations

import json
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from site_zero.agents.scp173 import load_all_entities
from site_zero.ollama_client import ollama_chat_json, ollama_generate_sync, parse_scp079_actions_json
from site_zero.settings import AppSettings
from site_zero.tools.registry import call_tool, register_phase2_tools
from site_zero.world.layout import room_graph_for_meta
from site_zero.world_state import WorldStateStore


class Scp079GraphState(TypedDict, total=False):
    tick: int
    entities: dict[str, dict[str, Any]]
    rooms: dict[str, dict[str, Any]]
    meta: dict[str, Any]
    actions: list[dict[str, Any]]
    execution_log: list[str]
    policy: str


def observe_scp079_state(store: WorldStateStore, tick: int) -> Scp079GraphState:
    return {
        "tick": tick,
        "entities": load_all_entities(store),
        "rooms": store.get_rooms(),
        "meta": store.get_meta(),
        "actions": [],
        "execution_log": [],
    }


def execute_scp079_actions(store: WorldStateStore, actions: list[dict[str, Any]]) -> list[str]:
    registry = register_phase2_tools()
    logs: list[str] = []
    ctx: dict[str, Any] = {}
    for act in actions:
        name = act.get("tool")
        params = act.get("params")
        if not isinstance(name, str) or not isinstance(params, dict):
            continue
        res = call_tool(name, store, ctx, params, registry=registry)
        logs.append(f"{name}({params}) -> {res}")
    return logs


def _use_llm_for_079(settings: AppSettings) -> bool:
    return bool(settings.agents.use_llm or settings.scp079.use_llm)


def _plan_rules(state: Scp079GraphState) -> list[dict[str, Any]]:
    """Deterministic containment policy — no LLM."""
    entities = state.get("entities", {})
    rooms = state.get("rooms", {})
    meta = state.get("meta", {})
    actions: list[dict[str, Any]] = []

    s173 = entities.get("SCP-173", {})
    s173_room = s173.get("location", {}).get("room")
    if not isinstance(s173_room, str) or not s173_room:
        return actions

    graph = room_graph_for_meta(meta)
    neighbors = list(graph.get(s173_room, {}).get("neighbors", []))
    observable = bool(s173.get("observable", True))
    last_noise = meta.get("last_noise_by_room", {})
    if not isinstance(last_noise, dict):
        last_noise = {}

    alive_in_cell = any(
        e.get("kind") == "d_class" and e.get("alive", True)
        for e in entities.values()
        if e.get("location", {}).get("room") == s173_room
    )

    max_nb_noise = 0.0
    loudest_nb: str | None = None
    for nb in neighbors:
        n = float(last_noise.get(nb, 0.0))
        if n > max_nb_noise:
            max_nb_noise = n
            loudest_nb = nb

    if not alive_in_cell:
        for nb in neighbors:
            actions.append({"tool": "set_room_lock", "params": {"room_id": nb, "is_locked": True}})
        actions.append(
            {"tool": "set_room_light", "params": {"room_id": s173_room, "light_level": 0.3}},
        )
        return actions

    if max_nb_noise >= 26.0 and loudest_nb:
        actions.append({"tool": "set_room_lock", "params": {"room_id": loudest_nb, "is_locked": True}})

    if not observable:
        cur = float(rooms.get(s173_room, {}).get("light_level", 0.5))
        target = max(cur, 0.94)
        actions.append(
            {"tool": "set_room_light", "params": {"room_id": s173_room, "light_level": target}},
        )

    if max_nb_noise < 12.0:
        for nb in neighbors:
            if bool(rooms.get(nb, {}).get("is_locked")):
                actions.append({"tool": "set_room_lock", "params": {"room_id": nb, "is_locked": False}})

    return actions


def _plan_llm(state: Scp079GraphState, settings: AppSettings) -> list[dict[str, Any]]:
    snap = {
        "tick": state.get("tick", 0),
        "entities": state.get("entities", {}),
        "rooms": state.get("rooms", {}),
        "meta": state.get("meta", {}),
    }
    prompt = (
        "You are SCP-079 (site control AI). Output ONLY valid JSON with this shape:\n"
        '{"actions":[{"tool":"set_room_light","params":{"room_id":"containment-173",'
        '"light_level":0.0}},{"tool":"set_room_lock","params":{"room_id":"corridor-east-a",'
        '"is_locked":false}}]}\n'
        "Allowed tools: set_room_light (light_level 0..1), set_room_lock (is_locked bool). "
        "Rooms: containment-173, corridor-east-a. "
        "Raise lights in containment when SCP-173 was not observable; lock corridor on high noise. "
        "Site snapshot:\n"
        + json.dumps(snap, default=str)[:12000]
    )
    try:
        raw = ollama_generate_sync(
            settings.ollama.base_url,
            settings.ollama.model,
            prompt,
            timeout=settings.ollama.timeout_seconds,
            temperature=0.1,
            json_mode=True,
        )
        parsed = [{"tool": a["tool"], "params": a["params"]} for a in parse_scp079_actions_json(raw)]
        cleaned = sanitize_scp079_actions(parsed)
        return cleaned if cleaned else _plan_rules(state)
    except Exception:
        return _plan_rules(state)


_VALID_TOOLS = frozenset({"set_room_light", "set_room_lock"})


def _normalize_action_params(tool: str, params: dict[str, Any]) -> dict[str, Any] | None:
    if tool == "set_room_light":
        rid = params.get("room_id")
        if not isinstance(rid, str):
            return None
        try:
            lv = float(params.get("light_level", 0.5))
        except (TypeError, ValueError):
            return None
        return {"room_id": rid, "light_level": max(0.0, min(1.0, lv))}
    if tool == "set_room_lock":
        rid = params.get("room_id")
        if not isinstance(rid, str):
            return None
        locked = params.get("is_locked", params.get("lock_status"))
        if not isinstance(locked, bool):
            if isinstance(locked, str):
                locked = locked.lower() in ("1", "true", "yes", "locked")
            else:
                locked = bool(locked)
        return {"room_id": rid, "is_locked": locked}
    return None


def sanitize_scp079_actions(raw_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop hallucinated tool names; normalize param keys."""
    out: list[dict[str, Any]] = []
    for a in raw_actions:
        if not isinstance(a, dict):
            continue
        t = str(a.get("tool", "")).strip()
        if "|" in t or t not in _VALID_TOOLS:
            continue
        params = a.get("params")
        if not isinstance(params, dict):
            continue
        norm = _normalize_action_params(t, params)
        if norm is None:
            continue
        out.append({"tool": t, "params": norm})
    return out


def actions_from_chat_json(data: dict[str, Any]) -> list[dict[str, Any]]:
    if not data:
        return []
    actions = data.get("actions")
    if isinstance(actions, list):
        raw: list[dict[str, Any]] = []
        for a in actions:
            if isinstance(a, dict) and isinstance(a.get("tool"), str) and isinstance(a.get("params"), dict):
                raw.append({"tool": a["tool"], "params": a["params"]})
        return sanitize_scp079_actions(raw)
    return []


async def plan_scp079_llm_async(
    settings: AppSettings,
    state: Scp079GraphState,
    client: httpx.AsyncClient,
    *,
    memory_context: str = "",
) -> list[dict[str, Any]]:
    snap = {
        "tick": state.get("tick", 0),
        "entities": state.get("entities", {}),
        "rooms": state.get("rooms", {}),
        "meta": state.get("meta", {}),
    }
    system = (
        "You are SCP-079, an on-site control AI. Reply with JSON only. "
        'Shape: {"actions":[{"tool":"set_room_light","params":{"room_id":"containment-173","light_level":0.8}},'
        '{"tool":"set_room_lock","params":{"room_id":"corridor-east-a","is_locked":true}}]} '
        "Rules: each item has exactly one tool string — either set_room_light OR set_room_lock, never combined. "
        "set_room_lock params must use is_locked (boolean). Rooms: containment-173, corridor-east-a."
    )
    user = "Site snapshot:\n" + json.dumps(snap, default=str)[:12000]
    if memory_context.strip():
        user = memory_context.strip() + "\n\n" + user
    data = await ollama_chat_json(
        client,
        settings.ollama.base_url,
        settings.ollama.model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        timeout=settings.ollama.timeout_seconds,
        temperature=0.15,
    )
    acts = actions_from_chat_json(data)
    return acts if acts else _plan_rules(state)


def build_scp079_graph(store: WorldStateStore, settings: AppSettings):  # CompiledStateGraph
    def observe(state: Scp079GraphState) -> Scp079GraphState:
        return observe_scp079_state(store, int(state.get("tick", 0)))

    def plan(state: Scp079GraphState) -> Scp079GraphState:
        if _use_llm_for_079(settings):
            actions = _plan_llm(state, settings)
            policy = "llm"
        else:
            actions = _plan_rules(state)
            policy = "rules"
        return {**state, "actions": actions, "policy": policy}

    def execute(state: Scp079GraphState) -> Scp079GraphState:
        logs = execute_scp079_actions(store, state.get("actions", []))
        return {**state, "execution_log": logs}

    graph = StateGraph(Scp079GraphState)
    graph.add_node("observe", observe)
    graph.add_node("plan", plan)
    graph.add_node("execute", execute)
    graph.add_edge(START, "observe")
    graph.add_edge("observe", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", END)
    return graph.compile()


def build_scp079_graph_rules_only(store: WorldStateStore, settings: AppSettings):
    """Force rules planner (for LLM fallback)."""
    s = settings.model_copy(deep=True)
    s.agents = s.agents.model_copy(update={"use_llm": False})
    s.scp079 = s.scp079.model_copy(update={"use_llm": False})
    return build_scp079_graph(store, s)
