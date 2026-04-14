"""Tkinter map implementation — imported only after tkinter is verified available."""

from __future__ import annotations

import argparse
import asyncio
import math
import threading
import tkinter as tk
import tkinter.ttk as ttk
from pathlib import Path
from typing import Any

from site_zero.settings import AppSettings, load_settings
from site_zero.world.layout import room_graph_for_meta
from site_zero.world_state import MemoryWorldState, WorldStateStore, connect_world_state


def _truncate_cell(s: str, max_len: int = 96) -> str:
    t = str(s).replace("\n", " ").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _life_status_line(ent: dict[str, Any]) -> str:
    """Short English label for roster panel (alive / dead / active)."""
    k = ent.get("kind")
    alive = ent.get("alive")
    if k == "d_class":
        return "alive" if alive is not False else "DEAD"
    if k == "scp":
        if alive is False:
            return "DEAD"
        if alive is True:
            return "alive"
        return "active"
    return "—"


def _status_row_tag(status_text: str) -> str:
    """Treeview row tag for ``tag_configure`` (foreground/background)."""
    s = str(status_text).strip().lower()
    if s == "dead":
        return "st_dead"
    if s == "alive":
        return "st_alive"
    if s == "active":
        return "st_active"
    return "st_muted"


def _apply_roster_row_tags(tree: ttk.Treeview) -> None:
    """Distinct row colors per status (clam theme)."""
    tree.tag_configure("st_alive", background="#0f2818", foreground="#8ee5b0")
    tree.tag_configure("st_dead", background="#2a1518", foreground="#f0a8a8")
    tree.tag_configure("st_active", background="#141a2e", foreground="#a8c4ff")
    tree.tag_configure("st_muted", background="#0f0f1a", foreground="#7a7a8a")


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
    """Place rooms using ``layout_xy`` when present; else hub-and-spoke fallback."""
    layout_ids = [rid for rid in graph if "layout_xy" in graph.get(rid, {})]
    if len(layout_ids) == len(graph) and layout_ids:
        xs = [float(graph[rid]["layout_xy"][0]) for rid in graph]  # type: ignore[index]
        ys = [float(graph[rid]["layout_xy"][1]) for rid in graph]  # type: ignore[index]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 0.08)
        span_y = max(max_y - min_y, 0.08)
        inner_w = cw - 2 * margin
        inner_h = ch - 2 * margin
        out: dict[str, tuple[float, float]] = {}
        for rid in graph:
            lx, ly = graph[rid]["layout_xy"]  # type: ignore[index]
            nx = (float(lx) - min_x) / span_x
            ny = (float(ly) - min_y) / span_y
            out[rid] = (margin + nx * inner_w, margin + ny * inner_h)
        return out

    cx, cy = cw / 2, ch / 2
    R = min(cw, ch) / 2 - margin
    hub = "site-hub" if "site-hub" in graph else None
    others = sorted(r for r in graph.keys() if r != hub)
    out_fb: dict[str, tuple[float, float]] = {}
    if hub:
        out_fb[hub] = (cx, cy)
        n = len(others)
        for i, rid in enumerate(others):
            ang = 2 * math.pi * i / max(n, 1) - math.pi / 2
            out_fb[rid] = (cx + R * 0.62 * math.cos(ang), cy + R * 0.62 * math.sin(ang))
        return out_fb
    n = len(others)
    for i, rid in enumerate(others):
        x = margin + (cw - 2 * margin) * (i + 1) / max(n + 1, 1)
        out_fb[rid] = (x, cy)
    return out_fb


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

        panel = tk.Frame(body, bg="#16213e", width=720)
        panel.pack(side=tk.RIGHT, fill=tk.Y, expand=False, padx=(8, 0))
        panel.pack_propagate(False)

        tk.Label(
            panel,
            text="Roster  ·  SCP | D-class  ·  drag center divider  ·  20× D-9001–9020",
            fg="#eaeaea",
            bg="#16213e",
            font=("Helvetica", 9, "bold"),
        ).pack(anchor="w", padx=6, pady=(6, 2))

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "SZ.Treeview",
            background="#0f0f1a",
            fieldbackground="#0f0f1a",
            foreground="#c8c8d0",
            font=("Helvetica", 8),
            rowheight=18,
        )
        style.configure(
            "SZ.Treeview.Heading",
            background="#243054",
            foreground="#eaeaea",
            font=("Helvetica", 9, "bold"),
        )
        style.map("SZ.Treeview", background=[("selected", "#3d5580")], foreground=[("selected", "#ffffff")])

        def _make_roster_tree(parent: tk.Frame, heading: str) -> ttk.Treeview:
            tk.Label(
                parent,
                text=heading,
                fg="#b8c8e8",
                bg="#16213e",
                font=("Helvetica", 9, "bold"),
            ).pack(anchor="w", pady=(0, 1))
            wrap = tk.Frame(parent, bg="#16213e")
            wrap.pack(fill=tk.BOTH, expand=True)
            scroll = ttk.Scrollbar(wrap)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            cols = ("id", "status", "room", "pos", "last")
            tree = ttk.Treeview(
                wrap,
                columns=cols,
                show="headings",
                style="SZ.Treeview",
                yscrollcommand=scroll.set,
                height=24,
            )
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scroll.config(command=tree.yview)
            # Compact widths so two panes fit side-by-side (~320px each at default sash).
            tree.column("id", width=76, minwidth=60, stretch=False, anchor="w")
            tree.column("status", width=42, minwidth=36, stretch=False, anchor="center")
            tree.column("room", width=62, minwidth=48, stretch=True, anchor="w")
            tree.column("pos", width=44, minwidth=40, stretch=False, anchor="e")
            tree.column("last", width=72, minwidth=48, stretch=True, anchor="w")
            tree.heading("id", text="ID")
            tree.heading("status", text="Stat")
            tree.heading("room", text="Room")
            tree.heading("pos", text="x,y")
            tree.heading("last", text="Last")
            _apply_roster_row_tags(tree)
            return tree

        paned = tk.PanedWindow(
            panel,
            orient=tk.HORIZONTAL,
            bg="#16213e",
            sashwidth=6,
            sashrelief=tk.FLAT,
            bd=0,
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 6))

        col_left = tk.Frame(paned, bg="#16213e")
        col_right = tk.Frame(paned, bg="#16213e")
        paned.add(col_left, minsize=268, stretch="always")
        paned.add(col_right, minsize=268, stretch="always")

        self.tree_scp = _make_roster_tree(col_left, "SCP")
        self.tree_d = _make_roster_tree(col_right, "D-class")

        self.txt_help = tk.Text(
            panel,
            height=5,
            bg="#0f0f1a",
            fg="#8899bb",
            font=("Helvetica", 9),
            wrap=tk.WORD,
            highlightthickness=0,
            borderwidth=0,
        )

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
            for tr in (self.tree_scp, self.tree_d):
                for iid in tr.get_children():
                    tr.delete(iid)
            self.txt_help.pack(fill=tk.X, padx=6, pady=(0, 6))
            self.txt_help.delete("1.0", tk.END)
            self.txt_help.insert(
                tk.END,
                "Map needs world data.\n\n"
                "• Redis: run `python -m site_zero` in another terminal, then `--gui`.\n"
                "• Or one process: `python -m site_zero --live`\n",
            )
            return

        self.txt_help.pack_forget()

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

        scp_rows: list[tuple[tuple[str, str, str, str, str], str]] = []
        d_rows: list[tuple[tuple[str, str, str, str, str], str]] = []
        for eid in sorted(entities):
            ent = entities[eid]
            loc = ent.get("location") or {}
            room = str(loc.get("room", "?"))
            last_raw = str((meta.get("last_status") or {}).get(eid, "—"))
            st = _life_status_line(ent)
            x, y = float(loc.get("x", 0)), float(loc.get("y", 0))
            pos_s = f"{x:.1f},{y:.1f}"
            last_cell = _truncate_cell(last_raw, 52)
            row_vals = (eid, st, room, pos_s, last_cell)
            tag = _status_row_tag(st)
            if ent.get("kind") == "scp":
                scp_rows.append((row_vals, tag))
            elif str(eid).startswith("D-") and ent.get("kind") == "d_class":
                d_rows.append((row_vals, tag))

        for eid, ent in sorted(entities.items()):
            if ent.get("kind") != "scp":
                continue
            loc = ent.get("location") or {}
            room = str(loc.get("room", "?"))
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

        for eid, ent in sorted(entities.items()):
            if ent.get("kind") != "d_class" or not str(eid).startswith("D-"):
                continue
            loc = ent.get("location") or {}
            room = str(loc.get("room", "?"))
            x, y = float(loc.get("x", 0)), float(loc.get("y", 0))
            rect = self._room_rects.get(room)
            if not rect:
                continue
            x0, y0, x1, y1 = rect
            mx = (x0 + x1) / 2 + max(-16, min(16, (x - 5) * 3.2))
            my = (y0 + y1) / 2 + max(-10, min(10, (y - 5) * 3.2))
            alive = ent.get("alive", True) is not False
            fill = "#4a6fa5" if alive else "#3d2020"
            outline = "#88aacc" if alive else "#cc4444"
            rd = 4
            self.canvas.create_rectangle(
                mx - rd, my - rd, mx + rd, my + rd,
                fill=fill,
                outline=outline,
                width=1,
            )

        for tree, rows in ((self.tree_scp, scp_rows), (self.tree_d, d_rows)):
            for iid in tree.get_children():
                tree.delete(iid)
            for row_vals, tag in rows:
                tree.insert("", tk.END, values=row_vals, tags=(tag,))
        try:
            self.root.update_idletasks()
        except tk.TclError:
            pass


def run_gui(*, config_path: Path | None = None) -> None:
    settings = load_settings(config_path)
    store = connect_world_state(settings.redis.url, settings.redis.enabled)
    root = tk.Tk()
    SiteMapApp(root, store, settings)
    root.minsize(1240, 620)
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
    root.minsize(1240, 620)
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Site-Zero live map (Tkinter + Redis)")
    _pkg_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--config", type=Path, default=_pkg_root / "config.yaml")
    args = parser.parse_args()
    run_gui(config_path=args.config)


if __name__ == "__main__":
    main()
