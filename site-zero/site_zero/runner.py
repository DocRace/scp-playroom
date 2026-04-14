"""Autonomous tick loop — SCP-079, D-class, SCP-173; optional narrative + vector memory."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

from site_zero.agents.d_class import apply_d_class_tick_async
from site_zero.agents.scp079 import apply_scp079_tick_async
from site_zero.agents.scp079_graph import observe_scp079_state
from site_zero.agents.scp173 import apply_scp173_tick_async, load_all_entities
from site_zero.memory.vector_memory import VectorAgentMemory, events_to_snippet, format_memory_prompt_block
from site_zero.ollama_client import ollama_available, ollama_generate
from site_zero.perception import render_scp173_context
from site_zero.scps.tick_dispatch import dispatch_scp_ticks_except_173
from site_zero.seed import ensure_world_seed
from site_zero.settings import AppSettings
from site_zero.world_state import MemoryWorldState, WorldStateStore, connect_world_state


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_line(level: str, msg: str, **extra: Any) -> None:
    tail = f" {extra}" if extra else ""
    print(f"[{_ts()}] [{level.upper()}] {msg}{tail}", flush=True)


def _agent_id_from_event(ev: dict[str, Any]) -> str | None:
    a = ev.get("agent")
    if isinstance(a, str) and a.strip():
        return a.strip()
    s = ev.get("scp_id")
    if isinstance(s, str) and s.strip():
        return s.strip()
    return None


def _merge_last_status(store: WorldStateStore, events: list[dict[str, Any]], *, tick: int) -> None:
    """Expose last log line per agent for the live map GUI (Redis poll)."""
    meta = store.get_meta()
    status: dict[str, str] = dict(meta.get("last_status") or {})
    for ev in events:
        aid = _agent_id_from_event(ev)
        msg = ev.get("msg")
        if not aid or not isinstance(msg, str) or not msg.strip():
            continue
        status[aid] = msg.strip()[:240]
    meta["last_status"] = status
    meta["sim_tick"] = tick
    store.set_meta(meta)


def _merge_noise_meta(store: WorldStateStore, events: list[dict[str, Any]]) -> None:
    merged: dict[str, float] = {}
    for ev in events:
        nm = ev.get("noise_db_by_room")
        if not isinstance(nm, dict):
            continue
        for k, v in nm.items():
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            merged[str(k)] = max(merged.get(str(k), 0.0), fv)
    if not merged:
        return
    meta = store.get_meta()
    meta["last_noise_by_room"] = merged
    store.set_meta(meta)


def _tick_settings_for_ollama(settings: AppSettings, ollama_ok: bool) -> AppSettings:
    if ollama_ok:
        return settings
    ts = settings.model_copy(deep=True)
    ts.agents = ts.agents.model_copy(update={"use_llm": False})
    ts.scp079 = ts.scp079.model_copy(update={"use_llm": False})
    return ts


async def run_simulation(
    settings: AppSettings,
    *,
    store: WorldStateStore | None = None,
    max_ticks: int | None = None,
    verbose: bool = False,
) -> None:
    if store is None:
        store = connect_world_state(settings.redis.url, settings.redis.enabled)
    ensure_world_seed(store, site_preset=settings.simulation.site_preset)

    _log_line("info", "Site-Zero heartbeat online", site=settings.simulation.site_id)
    tick = 0
    async with httpx.AsyncClient() as http:
        ollama_ok = await ollama_available(http, settings.ollama.base_url)
        if settings.agents.use_llm and ollama_ok:
            _log_line(
                "info",
                "Agent policy: Ollama JSON per tick (SCP-079, D-class, SCP-173)",
                model=settings.ollama.model,
            )
        elif settings.agents.use_llm and not ollama_ok:
            _log_line(
                "warn",
                "Agent LLM enabled in config but Ollama unreachable — rules-only ticks",
            )

        memory: VectorAgentMemory | None = None
        if settings.memory.enabled and ollama_ok:
            memory = VectorAgentMemory(settings)
            _log_line(
                "info",
                "Agent memory: Chroma + embeddings",
                chroma=settings.memory.chroma_path,
                embed_model=settings.memory.embedding_model,
            )

        if settings.ollama.narrative_enabled and not ollama_ok:
            _log_line("warn", "Ollama unreachable; narrative disabled for this session")
        elif settings.ollama.narrative_enabled:
            _log_line("info", "Ollama OK; narrative layer active", model=settings.ollama.model)

        while True:
            tick += 1
            tick_settings = _tick_settings_for_ollama(settings, ollama_ok)
            entities = load_all_entities(store)
            perception = render_scp173_context(entities, tick, store.get_rooms())
            if verbose:
                _log_line("debug", "--- perception ---\n" + perception)

            mem079 = ""
            mem173 = ""
            if memory:
                st079 = observe_scp079_state(store, tick)
                q079 = f"SCP-079 site tick {tick} " + json.dumps(st079, default=str)[:3500]
                lines079 = await memory.recall_lines(http, "SCP-079", q079)
                mem079 = format_memory_prompt_block(lines079)

            ev079 = await apply_scp079_tick_async(
                store,
                tick_settings,
                http,
                tick,
                memory_context=mem079,
            )
            for ev in ev079:
                _log_line(ev.get("level", "info"), ev.get("msg", ""))
            if memory:
                await memory.remember(
                    http,
                    "SCP-079",
                    events_to_snippet(ev079),
                    {"tick": tick, "kind": "scp079"},
                )

            entities = load_all_entities(store)
            d_ids = sorted(
                eid
                for eid in entities
                if str(eid).startswith("D-") and entities[eid].get("kind") == "d_class"
            )
            noise_accum: list[dict[str, Any]] = list(ev079)
            for idx, d_id in enumerate(d_ids):
                use_llm_d = bool(tick_settings.agents.use_llm) and idx < int(
                    tick_settings.agents.d_class_llm_max
                )
                mem_d = ""
                if memory and use_llm_d:
                    d_ent = entities.get(d_id, {})
                    q_d = f"{d_id} tick {tick} " + json.dumps(
                        {"self": d_ent, "rooms": store.get_rooms()},
                        default=str,
                    )[:3500]
                    lines_d = await memory.recall_lines(http, d_id, q_d)
                    mem_d = format_memory_prompt_block(lines_d)
                ev_d = await apply_d_class_tick_async(
                    store,
                    tick_settings,
                    http,
                    memory_context=mem_d,
                    entity_id=d_id,
                    use_llm=use_llm_d,
                )
                noise_accum.extend(ev_d)
                for ev in ev_d:
                    _log_line(ev.get("level", "info"), ev.get("msg", ""))
                if memory and use_llm_d:
                    await memory.remember(
                        http,
                        d_id,
                        events_to_snippet(ev_d),
                        {"tick": tick, "kind": "d_class"},
                    )

            ev_scp = await dispatch_scp_ticks_except_173(store, tick)
            noise_accum.extend(ev_scp)
            for ev in ev_scp:
                _log_line(ev.get("level", "info"), ev.get("msg", ""))

            entities = load_all_entities(store)
            perception173 = render_scp173_context(entities, tick, store.get_rooms())
            if memory:
                q173 = f"SCP-173 tick {tick} " + perception173[:3500]
                lines173 = await memory.recall_lines(http, "SCP-173", q173)
                mem173 = format_memory_prompt_block(lines173)

            events173 = await apply_scp173_tick_async(
                store,
                tick_settings,
                http,
                perception_md=perception173,
                memory_context=mem173,
            )
            noise_accum.extend(events173)
            for ev in events173:
                _log_line(ev.get("level", "info"), ev.get("msg", ""))
            if memory:
                await memory.remember(
                    http,
                    "SCP-173",
                    events_to_snippet(events173),
                    {"tick": tick, "kind": "scp173"},
                )

            _merge_noise_meta(store, noise_accum)
            _merge_last_status(store, noise_accum, tick=tick)

            if settings.ollama.narrative_enabled and ollama_ok:
                try:
                    prompt = (
                        "You are the Site-Zero log narrator. One or two terse sentences, "
                        "clinical tone, no gore. Context:\n" + perception173[:4000]
                    )
                    line = await ollama_generate(
                        http,
                        settings.ollama.base_url,
                        settings.ollama.model,
                        prompt,
                        timeout=settings.ollama.timeout_seconds,
                    )
                    _log_line("narrative", line.strip())
                except Exception as e:
                    _log_line("warn", f"narrative failed: {e}")

            if isinstance(store, MemoryWorldState):
                for ev in store.drain_events():
                    _log_line("event", str(ev))

            if max_ticks is not None and tick >= max_ticks:
                break

            await asyncio.sleep(settings.simulation.tick_interval_seconds)


def run_sync(
    settings: AppSettings,
    *,
    max_ticks: int | None = None,
    verbose: bool = False,
) -> None:
    try:
        asyncio.run(run_simulation(settings, max_ticks=max_ticks, verbose=verbose))
    except KeyboardInterrupt:
        _log_line("info", "Shutdown signal — Site-Zero tick loop stopped")
        sys.exit(0)
