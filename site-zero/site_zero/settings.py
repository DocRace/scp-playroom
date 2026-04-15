"""Load YAML config with environment overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from typing import Literal

from pydantic import BaseModel, Field


class RedisSettings(BaseModel):
    url: str = "redis://localhost:6379/0"
    enabled: bool = True


class SimulationSettings(BaseModel):
    tick_interval_seconds: float = 1.0
    site_id: str = "SITE-ZERO-01"
    site_preset: Literal["full", "minimal"] = Field(
        default="full",
        description="full = hub site + 20 SCPs + 20 D-class; minimal = legacy 173 corridor sandbox.",
    )


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama3.2:latest"
    timeout_seconds: float = 120.0
    narrative_enabled: bool = False


class PathHints(BaseModel):
    ollama_models_hint: str = "~/.ollama/models"


class Scp079Settings(BaseModel):
    """SCP-079 — site AI: lights and interlocks (LangGraph + rules or LLM policy)."""

    enabled: bool = True
    use_llm: bool = False


class AgentsSettings(BaseModel):
    """When use_llm is true, SCP-079 / D-class / SCP-173 each call Ollama JSON per tick (with rules fallback)."""

    use_llm: bool = True
    fallback_to_rules: bool = True
    d_class_llm_max: int = Field(
        default=3,
        description="Max D-class subjects per tick that call the LLM; others use rules.",
    )


class MemorySettings(BaseModel):
    """
    Per-agent episodic memory: Chroma on disk + Ollama embeddings (RAG).
    Pull embed model: `ollama pull nomic-embed-text`
    """

    enabled: bool = True
    chroma_path: str = "data/chroma_site_zero"
    embedding_model: str = "nomic-embed-text"
    recall_top_k: int = 6
    roster_recall: bool = Field(
        default=False,
        description="RAG recall + embed per roster SCP tick (many extra Ollama calls each tick).",
    )


class AppSettings(BaseModel):
    redis: RedisSettings = Field(default_factory=RedisSettings)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    agents: AgentsSettings = Field(default_factory=AgentsSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    scp079: Scp079Settings = Field(default_factory=Scp079Settings)
    paths: PathHints = Field(default_factory=PathHints)


def load_settings(config_path: str | Path | None = None) -> AppSettings:
    path = Path(
        config_path
        or os.environ.get("SITE_ZERO_CONFIG")
        or Path(__file__).resolve().parents[1] / "config.yaml"
    )
    data: dict[str, Any] = {}
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    settings = AppSettings.model_validate(data)
    # Env overrides (highest priority)
    if os.environ.get("SITE_ZERO_REDIS_URL"):
        settings.redis.url = os.environ["SITE_ZERO_REDIS_URL"]
    if os.environ.get("SITE_ZERO_REDIS_ENABLED", "").lower() in ("0", "false", "no"):
        settings.redis.enabled = False
    if os.environ.get("OLLAMA_BASE_URL"):
        settings.ollama.base_url = os.environ["OLLAMA_BASE_URL"].rstrip("/")
    if os.environ.get("SITE_ZERO_MODEL"):
        settings.ollama.model = os.environ["SITE_ZERO_MODEL"]
    if os.environ.get("SITE_ZERO_NARRATIVE", "").lower() in ("1", "true", "yes"):
        settings.ollama.narrative_enabled = True
    if os.environ.get("SITE_ZERO_SCP079", "").lower() in ("0", "false", "no"):
        settings.scp079.enabled = False
    if os.environ.get("SITE_ZERO_SCP079_LLM", "").lower() in ("1", "true", "yes"):
        settings.scp079.use_llm = True
    if os.environ.get("SITE_ZERO_AGENT_LLM", "").lower() in ("0", "false", "no"):
        settings.agents.use_llm = False
    if os.environ.get("SITE_ZERO_AGENT_LLM", "").lower() in ("1", "true", "yes"):
        settings.agents.use_llm = True
    if os.environ.get("SITE_ZERO_NO_RULES_FALLBACK", "").lower() in ("1", "true", "yes"):
        settings.agents.fallback_to_rules = False
    if os.environ.get("SITE_ZERO_MEMORY", "").lower() in ("0", "false", "no"):
        settings.memory.enabled = False
    if os.environ.get("SITE_ZERO_MEMORY", "").lower() in ("1", "true", "yes"):
        settings.memory.enabled = True
    if os.environ.get("SITE_ZERO_EMBED_MODEL"):
        settings.memory.embedding_model = os.environ["SITE_ZERO_EMBED_MODEL"]
    if os.environ.get("SITE_ZERO_ROSTER_RECALL", "").lower() in ("1", "true", "yes"):
        settings.memory = settings.memory.model_copy(update={"roster_recall": True})
    if os.environ.get("SITE_ZERO_ROSTER_RECALL", "").lower() in ("0", "false", "no"):
        settings.memory = settings.memory.model_copy(update={"roster_recall": False})
    if raw_dc := os.environ.get("SITE_ZERO_D_CLASS_LLM_MAX", "").strip():
        try:
            settings.agents = settings.agents.model_copy(
                update={"d_class_llm_max": max(0, int(raw_dc))},
            )
        except ValueError:
            pass
    sp = os.environ.get("SITE_ZERO_SITE_PRESET", "").lower().strip()
    if sp in ("full", "minimal"):
        sim = settings.simulation.model_dump()
        sim["site_preset"] = sp
        settings.simulation = SimulationSettings.model_validate(sim)
    return settings
