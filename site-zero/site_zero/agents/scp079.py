"""SCP-079 tick — LangGraph site controller; async LLM path when enabled."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from site_zero.agents.scp079_graph import (
    _use_llm_for_079,
    build_scp079_graph,
    build_scp079_graph_rules_only,
    execute_scp079_actions,
    observe_scp079_state,
    plan_scp079_llm_async,
)
from site_zero.settings import AppSettings
from site_zero.world_state import WorldStateStore


def _rows_from_state(st: dict[str, Any], tick: int) -> list[dict[str, Any]]:
    policy = st.get("policy", "?")
    rows: list[dict[str, Any]] = [
        {
            "level": "info",
            "msg": f"SCP-079 tick={tick} policy={policy}",
            "agent": "SCP-079",
        }
    ]
    for line in st.get("execution_log", []):
        rows.append({"level": "warn", "msg": f"SCP-079 ▸ {line}", "agent": "SCP-079"})
    return rows


def apply_scp079_tick(
    store: WorldStateStore,
    settings: AppSettings,
    tick: int,
) -> list[dict[str, Any]]:
    if not settings.scp079.enabled:
        return []
    graph = build_scp079_graph(store, settings)
    st = graph.invoke({"tick": tick})
    rows = _rows_from_state(st, tick)
    store.publish(
        "site_zero:broadcast",
        {"type": "scp079_tick", "tick": tick, "policy": st.get("policy", "?")},
    )
    return rows


async def apply_scp079_tick_async(
    store: WorldStateStore,
    settings: AppSettings,
    http: httpx.AsyncClient,
    tick: int,
    *,
    memory_context: str = "",
) -> list[dict[str, Any]]:
    if not settings.scp079.enabled:
        return []
    if _use_llm_for_079(settings):
        try:
            state = observe_scp079_state(store, tick)
            actions = await plan_scp079_llm_async(settings, state, http, memory_context=memory_context)
            logs = execute_scp079_actions(store, actions)
            st = {
                **state,
                "actions": actions,
                "execution_log": logs,
                "policy": "llm-async",
            }
            rows = _rows_from_state(st, tick)
            store.publish(
                "site_zero:broadcast",
                {"type": "scp079_tick", "tick": tick, "policy": "llm-async"},
            )
            return rows
        except Exception as exc:
            if not settings.agents.fallback_to_rules:
                return [{"level": "error", "msg": f"SCP-079 LLM failed: {exc}", "agent": "SCP-079"}]
            graph = build_scp079_graph_rules_only(store, settings)
            st = await asyncio.to_thread(graph.invoke, {"tick": tick})
            rows = _rows_from_state(st, tick)
            rows.insert(
                1,
                {"level": "warn", "msg": f"SCP-079 LLM fallback to rules ({exc})", "agent": "SCP-079"},
            )
            store.publish(
                "site_zero:broadcast",
                {"type": "scp079_tick", "tick": tick, "policy": "rules-fallback"},
            )
            return rows

    graph = build_scp079_graph(store, settings)
    st = await asyncio.to_thread(graph.invoke, {"tick": tick})
    rows = _rows_from_state(st, tick)
    store.publish(
        "site_zero:broadcast",
        {"type": "scp079_tick", "tick": tick, "policy": st.get("policy", "?")},
    )
    return rows
