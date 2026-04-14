"""Tkinter map implementation — imported only after tkinter is verified available."""

from __future__ import annotations

import argparse
import asyncio
import math
import threading
import tkinter as tk
from pathlib import Path
from typing import Any

from site_zero.settings import AppSettings, load_settings
from site_zero.world.layout import room_graph_for_meta
from site_zero.world_state import MemoryWorldState, WorldStateStore, connect_world_state


def _stable_color(eid: str) -> str:
    h = hash(eid) & 0xFFFFFF
    r = 80 + ((h >> 16) & 0x7F)
    g = 80 + ((h >> 8) & 0x7F)
    b = 80 + (h & 0x7F)
    return f"#{r:02x}{g:02x}{b:02x}"


def _room_centers(
    graph: dict[str, dict[str, Any]],
    cw: int,
    ch: int,
    margin: int,
) -> dict[str, tuple[float, float]]:
    cx, cy = cw / 2, ch / 2
    R = min(cw, ch) / 2 - margin
    hub = "site-hub" if "site-hub" in graph else None
    others = sorted(r for r in graph.keys() if r != hub)
    out: dict[str, tuple[float, float]] = {}
    if hub:
        out[hub] = (cx, cy)
        n = len(others)
        for i, rid in enumerate(others):
            ang = 2 * math.pi * i / max(n, 1) - math.pi / 2
            out[rid] = (cx + R * 0.62 * math.cos(ang), cy + R * 0.62 * math.sin(ang))
        return out
    n = len(others)
    for i, rid in enumerate(others):
        x = margin + (cw - 2 * margin) * (i + 1) / max(n + 1, 1)
        out[rid] = (x, cy)
    return out


class SiteMapApp:
    def __init__(
        self,
        root: tk.Tk,
        store: WorldStateStore,
        settings: AppSettings,
        *,
        shared_memory_with_sim: bool = False,
    ) -> None:
        self.root = root
        self.store = store
        self.settings = settings
        self._shared_memory_with_sim = shared_memory_with_sim
        self._memory = isinstance(store, MemoryWorldState)

        root.title("Site-Zero — live map")
        root.configure(bg="#1a1a2e")

        top = tk.Frame(root, bg="#1a1a2e")
        top.pack(fill=tk.X, padx=8, pady=6)
        self.lbl_tick = tk.Label(
            top,
            text="tick: —",
            fg="#eaeaea",
            bg="#1a1a2e",
            font=("Helvetica", 12, "bold"),
        )
        self.lbl_tick.pack(side=tk.LEFT)
        self.lbl_warn = tk.Label(
            top,
            text="",
            fg="#ffcc66",
            bg="#1a1a2e",
            font=("Helvetica", 10),
        )
        self.lbl_warn.pack(side=tk.RIGHT)

        body = tk.Frame(root, bg="#1a1a2e")
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.canvas = tk.Canvas(
            body,
            width=720,
            height=560,
            bg="#0f0f1a",
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        panel = tk.Frame(body, bg="#16213e", width=300)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        panel.pack_propagate(False)

        tk.Label(
            panel,
            text="Agents — last action (SCP + D-class)",
            fg="#eaeaea",
            bg="#16213e",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self.txt = tk.Text(
            panel,
            width=36,
            height=32,
            bg="#0f0f1a",
            fg="#c8c8d0",
            font=("Courier", 10),
            wrap=tk.WORD,
            highlightthickness=0,
            borderwidth=0,
        )
        self.txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        self._room_rects: dict[str, tuple[float, float, float, float]] = {}
        self._poll_ms = 200
        self.root.after(self._poll_ms, self._refresh)

    def _refresh(self) -> None:
        try:
            self._draw_frame()
        except Exception as exc:
            self.lbl_warn.config(text=f"poll error: {exc}")
        self.root.after(self._poll_ms, self._refresh)

    def _draw_frame(self) -> None:
        if self._memory and not self._shared_memory_with_sim:
            self.lbl_warn.config(
                text="In-memory store — use Redis + second terminal, or run with --live.",
            )
            self.canvas.delete("all")
            self.txt.delete("1.0", tk.END)
            self.txt.insert(
                tk.END,
                "Map needs world data.\n\n"
                "• Redis: run `python -m site_zero` in another terminal, then `--gui`.\n"
                "• Or one process: `python -m site_zero --live`\n",
            )
            return

        if self._shared_memory_with_sim:
            self.lbl_warn.config(text="Embedded sim — shared memory (no Redis)")
        else:
            self.lbl_warn.config(text="")

        meta = self.store.get_meta()
        tick = meta.get("sim_tick", "—")
        phase = str(meta.get("tick_phase", "") or "").strip()
        phase_s = f" · {phase}" if phase else ""
        self.lbl_tick.config(
            text=f"tick: {tick}{phase_s}  ·  {self.settings.simulation.site_id}",
        )

        graph = room_graph_for_meta(meta)
        cw = int(self.canvas.winfo_width() or 720)
        ch = int(self.canvas.winfo_height() or 560)
        if cw < 50 or ch < 50:
            cw, ch = 720, 560

        margin = 48
        centers = _room_centers(graph, cw, ch, margin)
        rw, rh = 56, 40

        self.canvas.delete("all")
        self._room_rects.clear()

        drawn_e: set[tuple[str, str]] = set()
        for rid, (cx, cy) in centers.items():
            for nb in graph.get(rid, {}).get("neighbors", []):
                a, b = (rid, nb) if rid < nb else (nb, rid)
                if (a, b) in drawn_e:
                    continue
                drawn_e.add((a, b))
                p2 = centers.get(nb)
                if p2:
                    self.canvas.create_line(cx, cy, p2[0], p2[1], fill="#2a3550", width=1)

        for rid, (cx, cy) in centers.items():
            x0, y0 = cx - rw / 2, cy - rh / 2
            x1, y1 = cx + rw / 2, cy + rh / 2
            self._room_rects[rid] = (x0, y0, x1, y1)
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline="#3a4a6e",
                fill="#1a2238",
                width=1,
                tags=("room", rid),
            )
            short = rid.replace("con-", "C-").replace("site-", "")[:14]
            self.canvas.create_text(cx, cy - rh / 2 - 8, text=short, fill="#8899bb", font=("Helvetica", 8))

        entities: dict[str, dict[str, Any]] = {}
        for eid in self.store.list_entity_ids():
            e = self.store.get_entity(eid)
            if e:
                entities[eid] = e

        scp_lines: list[str] = []
        d_lines: list[str] = []
        for eid in sorted(entities):
            ent = entities[eid]
            loc = ent.get("location") or {}
            room = str(loc.get("room", "?"))
            last = (meta.get("last_status") or {}).get(eid, "—")
            if ent.get("kind") == "scp":
                x, y = float(loc.get("x", 0)), float(loc.get("y", 0))
                scp_lines.append(f"{eid}\n  room {room} @ ({x:.1f},{y:.1f})\n  {last}\n")
            elif str(eid).startswith("D-") and ent.get("kind") == "d_class":
                short_last = str(last).replace("\n", " ")[:100]
                d_lines.append(f"{eid}  [{room}]  {short_last}")

            if ent.get("kind") != "scp":
                continue
            x, y = float(loc.get("x", 0)), float(loc.get("y", 0))
            rect = self._room_rects.get(room)
            if rect:
                x0, y0, x1, y1 = rect
                mx = (x0 + x1) / 2 + max(-18, min(18, (x - 5) * 3.5))
                my = (y0 + y1) / 2 + max(-12, min(12, (y - 5) * 3.5))
            else:
                mx = cw / 2
                my = ch / 2

            r = 7
            self.canvas.create_oval(
                mx - r, my - r, mx + r, my + r,
                fill=_stable_color(eid),
                outline="#ffffff",
                width=1,
            )
            label = eid.replace("SCP-", "").replace("____", "..")[:12]
            self.canvas.create_text(mx + 12, my, text=label, fill="#e0e0e8", anchor="w", font=("Helvetica", 9))

        self.txt.delete("1.0", tk.END)
        blocks: list[str] = []
        if scp_lines:
            blocks.append("--- SCP ---\n" + "\n".join(scp_lines))
        else:
            blocks.append("(no SCP entities)")
        if d_lines:
            blocks.append("--- D-class ---\n" + "\n".join(sorted(d_lines)[:32]))
        self.txt.insert(tk.END, "\n\n".join(blocks))
        try:
            self.root.update_idletasks()
        except tk.TclError:
            pass


def run_gui(*, config_path: Path | None = None) -> None:
    settings = load_settings(config_path)
    store = connect_world_state(settings.redis.url, settings.redis.enabled)
    root = tk.Tk()
    SiteMapApp(root, store, settings)
    root.minsize(880, 600)
    root.mainloop()


def run_gui_live(
    settings: AppSettings,
    *,
    max_ticks: int | None = None,
    verbose: bool = False,
) -> None:
    from site_zero.runner import run_simulation

    shared = MemoryWorldState()

    def sim_loop() -> None:
        asyncio.run(
            run_simulation(
                settings,
                store=shared,
                max_ticks=max_ticks,
                verbose=verbose,
            )
        )

    threading.Thread(target=sim_loop, name="site-zero-sim", daemon=True).start()
    root = tk.Tk()
    SiteMapApp(root, shared, settings, shared_memory_with_sim=True)
    root.minsize(880, 600)
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Site-Zero live map (Tkinter + Redis)")
    _pkg_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--config", type=Path, default=_pkg_root / "config.yaml")
    args = parser.parse_args()
    run_gui(config_path=args.config)


if __name__ == "__main__":
    main()
