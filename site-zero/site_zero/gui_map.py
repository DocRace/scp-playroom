"""Live site map entry — loads Tkinter UI only when --gui / --live (see gui_tk.map_view)."""

from __future__ import annotations

import sys
from pathlib import Path

from site_zero.settings import AppSettings

_TKINTER_HINT = """
Tkinter is not available in this Python build (missing _tkinter).

Fix on macOS + Homebrew:
  brew install python-tk@3.13
This installs the _tkinter module for Homebrew python@3.13. Recreate the venv with that Python:
  cd site-zero
  rm -rf .venv
  "$(brew --prefix python@3.13)/bin/python3.13" -m venv .venv
  source .venv/bin/activate
  pip install -e .

Or install Python from https://www.python.org/downloads/ (includes Tk) and use that for the venv.

Then run: python -m site_zero --live
""".strip()


def _ensure_tkinter() -> None:
    try:
        import tkinter  # noqa: F401
    except ImportError as e:
        print(_TKINTER_HINT, file=sys.stderr)
        raise SystemExit(1) from e


def run_gui(*, config_path: Path | None = None) -> None:
    _ensure_tkinter()
    from site_zero.gui_tk.map_view import run_gui as _run

    _run(config_path=config_path)


def run_gui_live(
    settings: AppSettings,
    *,
    max_ticks: int | None = None,
    verbose: bool = False,
) -> None:
    _ensure_tkinter()
    from site_zero.gui_tk.map_view import run_gui_live as _run

    _run(settings, max_ticks=max_ticks, verbose=verbose)


def main() -> None:
    _ensure_tkinter()
    from site_zero.gui_tk.map_view import main as _main

    _main()


if __name__ == "__main__":
    main()
