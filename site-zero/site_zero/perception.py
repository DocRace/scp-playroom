"""Render Redis-style entity blobs into Markdown for agents (Jinja2)."""

from __future__ import annotations

from typing import Any

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

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
    tpl = _env.get_template("scp173_perception.md.j2")
    return tpl.render(entities=entities, tick=tick, rooms=rooms or {})
