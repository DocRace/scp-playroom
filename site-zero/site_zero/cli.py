"""CLI entry for Project Site-Zero."""

from __future__ import annotations

import argparse
from pathlib import Path

from site_zero.runner import run_sync
from site_zero.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Project Site-Zero — SCP computational sandbox (Phase 1–2)",
    )
    _pkg_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--config",
        type=Path,
        default=_pkg_root / "config.yaml",
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=None,
        help="Stop after N ticks (default: run until Ctrl+C)",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="Force in-process memory store (skip Redis)",
    )
    parser.add_argument(
        "--narrative",
        action="store_true",
        help="Enable Ollama one-line narrative per tick (slow)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print Jinja perception markdown each tick",
    )
    parser.add_argument(
        "--no-scp079",
        action="store_true",
        help="Disable SCP-079 / Phase-2 site control (SCP-173 only)",
    )
    parser.add_argument(
        "--scp079-llm",
        action="store_true",
        help="Also allow SCP-079-only LLM flag (combined with agents.use_llm)",
    )
    parser.add_argument(
        "--rules-only",
        action="store_true",
        help="Disable LLM for all agents (deterministic rules only)",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable per-agent Chroma vector memory",
    )
    parser.add_argument(
        "--site",
        choices=["full", "minimal"],
        default=None,
        help="World preset: full hub + 20 SCPs + 20 D-class, or minimal 173 sandbox",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open live map window (Tkinter); run the simulator in another terminal with Redis",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run simulation + map in one process (shared memory); uses config LLM settings",
    )
    args = parser.parse_args()
    settings = load_settings(args.config)
    if args.memory:
        settings.redis.enabled = False
    if args.narrative:
        settings.ollama.narrative_enabled = True
    if args.no_scp079:
        settings.scp079.enabled = False
    if args.scp079_llm:
        settings.scp079.use_llm = True
    if args.rules_only:
        settings.agents.use_llm = False
        settings.scp079.use_llm = False
    if args.no_memory:
        settings.memory.enabled = False
    if args.site:
        settings.simulation = settings.simulation.model_copy(update={"site_preset": args.site})

    if args.live:
        from site_zero.gui_map import run_gui_live

        run_gui_live(settings, max_ticks=args.ticks, verbose=args.verbose)
        return
    if args.gui:
        from site_zero.gui_map import run_gui

        run_gui(config_path=args.config)
        return

    run_sync(settings, max_ticks=args.ticks, verbose=args.verbose)


if __name__ == "__main__":
    main()
