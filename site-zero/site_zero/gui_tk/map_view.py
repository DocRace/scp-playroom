"""Tkinter map implementation — imported only after tkinter is verified available."""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
import threading
import tkinter as tk
import tkinter.scrolledtext as scrolledtext
import tkinter.ttk as ttk
from pathlib import Path
from typing import Any

from site_zero.gui_tk.entity_personas import build_chat_system_prompt
from site_zero.gui_tk.roleplay_client import ollama_roleplay_chat
from site_zero.perception_pov import pov_snapshot_for_entity
from site_zero.settings import AppSettings, load_settings
from site_zero.world.layout import room_graph_for_meta
from site_zero.world_state import MemoryWorldState, WorldStateStore, connect_world_state


def _silence_macos_imk_stderr() -> None:
    """Drop harmless Tk/InputMethodKit noise on macOS (stderr line from AppKit)."""
    if sys.platform != "darwin":
        return
    real = sys.stderr

    class _Filter:
        __slots__ = ("_r",)

        def __init__(self, r: Any) -> None:
            self._r = r

        def write(self, s: str) -> int:
            if isinstance(s, str) and "IMKCFRunLoopWakeUpReliable" in s:
                return len(s)
            return self._r.write(s)

        def flush(self) -> None:
            self._r.flush()

        def __getattr__(self, name: str) -> Any:
            return getattr(self._r, name)

    sys.stderr = _Filter(real)


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
    # Matches map cyan dashed ring (#3dd6e0) for the agent currently stepping in this tick.
    tree.tag_configure("tick_active", background="#0d2f36", foreground="#6ee8f0")


def _short_ollama_url(url: str, max_len: int = 36) -> str:
    u = str(url).replace("http://", "").replace("https://", "").rstrip("/")
    if len(u) <= max_len:
        return u
    return u[: max_len - 1] + "…"


def _ollama_banner(meta: dict[str, Any], settings: AppSettings) -> tuple[str, str]:
    """Return (label_text, foreground_hex) for the top Ollama status strip."""
    reach = meta.get("ollama_reachable")
    model = str(meta.get("ollama_model") or settings.ollama.model or "—")
    base = str(meta.get("ollama_base_url") or settings.ollama.base_url or "")
    base_s = _short_ollama_url(base) if base else "—"
    agents_cfg = bool(meta.get("agents_use_llm_config", settings.agents.use_llm))
    scp079_cfg = bool(meta.get("scp079_use_llm_config", settings.scp079.use_llm))
    narr_cfg = bool(meta.get("ollama_narrative_config", settings.ollama.narrative_enabled))

    if reach is None:
        return (
            f"Ollama: waiting… ·  {base_s}  ·  model {model}",
            "#8899bb",
        )
    if reach:
        bits = ["Ollama: connected", base_s, model]
        if agents_cfg or scp079_cfg:
            bits.append("agent LLM on")
        else:
            bits.append("agent LLM off (config)")
        if narr_cfg:
            bits.append("narrative on")
        return " ·  ".join(bits), "#8ee5b0"

    bits2 = ["Ollama: unreachable", base_s]
    if agents_cfg or scp079_cfg or narr_cfg:
        bits2.append("using rules-only / narrative off")
        return "  ·  ".join(bits2), "#ffaa66"
    bits2.append("LLM features off (config)")
    return "  ·  ".join(bits2), "#7a7a8a"


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


def _parse_light_level(room_blob: dict[str, Any] | None) -> float:
    if not room_blob:
        return 0.62
    try:
        return max(0.0, min(1.0, float(room_blob.get("light_level", 0.62))))
    except (TypeError, ValueError):
        return 0.62


def _room_fill_for_light(light_level: float) -> str:
    """Slightly brighten room tile when lights are up (same hue family as base #1a2238)."""
    base_r, base_g, base_b = 0x1A, 0x22, 0x38
    f = 0.42 + 0.58 * light_level
    r = int(min(255, base_r * f))
    g = int(min(255, base_g * f))
    b = int(min(255, base_b * f))
    return f"#{r:02x}{g:02x}{b:02x}"


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
        self.lbl_ollama = tk.Label(
            top,
            text="Ollama: …",
            fg="#8899bb",
            bg="#1a1a2e",
            font=("Helvetica", 10),
            anchor="w",
        )
        self.lbl_ollama.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(14, 8))
        self.lbl_warn = tk.Label(
            top,
            text="",
            fg="#ffcc66",
            bg="#1a1a2e",
            font=("Helvetica", 10),
        )
        self.lbl_warn.pack(side=tk.RIGHT)

        self._map_legend_full = (
            "Map: room darkness ∝ light; amber outline = locked. "
            "On each link, a dot toward a room = that room is locked (extra noise loss into it when sound crosses from the neighbor). "
            "dB pair (alphabetical room id order) = nominal loss when noise leaves each end. "
            "Passage is not movement-blocked by locks in this build."
        )
        self._map_legend = tk.Label(
            root,
            text=self._map_legend_full,
            fg="#7a8fb8",
            bg="#1a1a2e",
            font=("Helvetica", 8),
            anchor="w",
            justify=tk.LEFT,
            wraplength=1180,
        )
        self._map_legend.pack(fill=tk.X, padx=10, pady=(0, 2))

        self._outer = tk.PanedWindow(
            root,
            orient=tk.VERTICAL,
            bg="#1a1a2e",
            sashwidth=6,
            sashrelief=tk.FLAT,
            bd=0,
        )
        self._outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        upper = tk.Frame(self._outer, bg="#1a1a2e")
        self._outer.add(upper, minsize=380, stretch="always")

        body = tk.Frame(upper, bg="#1a1a2e")
        body.pack(fill=tk.BOTH, expand=True)

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
        style.map(
            "SZ.Treeview",
            background=[("selected", "#3d5580")],
            foreground=[("selected", "#ffffff")],
        )

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

        chat_shell = tk.Frame(self._outer, bg="#12121c")
        self._outer.add(chat_shell, minsize=200, stretch="always")
        self._chat_messages: dict[str, list[dict[str, str]]] = {}
        self._chat_busy = False
        self._chat_entity_var = tk.StringVar(value="")
        self._setup_agent_chat(chat_shell)

        self.tree_scp.bind("<Double-1>", lambda _e: self._pick_chat_from_tree(self.tree_scp))
        self.tree_d.bind("<Double-1>", lambda _e: self._pick_chat_from_tree(self.tree_d))
        self.tree_scp.bind("<<TreeviewSelect>>", lambda _e: self._on_roster_select(self.tree_scp))
        self.tree_d.bind("<<TreeviewSelect>>", lambda _e: self._on_roster_select(self.tree_d))

        self._room_rects: dict[str, tuple[float, float, float, float]] = {}
        self._map_highlight_eid: str | None = None
        self._roster_repainting: bool = False
        self._poll_ms = 200
        self.root.after(self._poll_ms, self._refresh)

    def _setup_agent_chat(self, parent: tk.Frame) -> None:
        """Bottom panel: select SCP or D-class, in-character chat (Ollama worker thread)."""
        tk.Label(
            parent,
            text="In-character chat  ·  parallel to the sim (context refreshed each send)  ·  double-click roster row to pick",
            fg="#a8b8d8",
            bg="#12121c",
            font=("Helvetica", 9, "bold"),
        ).pack(anchor="w", padx=8, pady=(6, 2))

        row = tk.Frame(parent, bg="#12121c")
        row.pack(fill=tk.X, padx=8, pady=(0, 4))
        tk.Label(row, text="Talk to:", fg="#c8c8d8", bg="#12121c", font=("Helvetica", 9)).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self.chat_combo = ttk.Combobox(
            row,
            textvariable=self._chat_entity_var,
            state="disabled",
            width=28,
        )
        self.chat_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.chat_combo.bind("<<ComboboxSelected>>", lambda _e: self._render_chat_transcript())

        self.chat_clear_btn = tk.Button(
            row,
            text="Clear log",
            command=self._clear_active_chat,
            font=("Helvetica", 9),
            bg="#243054",
            fg="#eaeaea",
            activebackground="#3d5580",
            activeforeground="#ffffff",
            relief=tk.FLAT,
        )
        self.chat_clear_btn.pack(side=tk.LEFT)

        self.chat_log = scrolledtext.ScrolledText(
            parent,
            height=9,
            bg="#0f0f1a",
            fg="#d8d8e4",
            insertbackground="#eaeaea",
            font=("Helvetica", 10),
            wrap=tk.WORD,
            highlightthickness=0,
            borderwidth=0,
        )
        self.chat_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        self.chat_log.config(state=tk.DISABLED)

        bot = tk.Frame(parent, bg="#12121c")
        bot.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.chat_entry = tk.Entry(
            bot,
            bg="#1a2238",
            fg="#eaeaea",
            insertbackground="#eaeaea",
            font=("Helvetica", 10),
            relief=tk.FLAT,
        )
        self.chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.chat_entry.bind("<Return>", lambda _e: self._send_chat_message())

        self.chat_send_btn = tk.Button(
            bot,
            text="Send",
            command=self._send_chat_message,
            font=("Helvetica", 10, "bold"),
            bg="#2e6f4f",
            fg="#ffffff",
            activebackground="#3d9070",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            state="disabled",
        )
        self.chat_send_btn.pack(side=tk.RIGHT)

    @staticmethod
    def _combo_values_list(combo: ttk.Combobox) -> list[str]:
        v = combo.cget("values")
        if isinstance(v, (tuple, list)):
            return [str(x) for x in v]
        if isinstance(v, str) and v.strip():
            return v.split()
        return []

    def _on_roster_select(self, tree: ttk.Treeview) -> None:
        """Single-click roster row: sticky map follow for that agent until you deselect the row."""
        if self._roster_repainting:
            return
        sel = tree.selection()
        if not sel:
            self._map_highlight_eid = None
            return
        vals = tree.item(sel[0], "values")
        if not vals:
            self._map_highlight_eid = None
            return
        self._map_highlight_eid = str(vals[0])

    def _restore_roster_tree_selection(self) -> None:
        """After repopulating roster tables, re-select the followed entity so polling does not drop the gold highlight."""
        follow = self._map_highlight_eid
        try:
            self.tree_scp.selection_remove(self.tree_scp.selection())
        except tk.TclError:
            pass
        try:
            self.tree_d.selection_remove(self.tree_d.selection())
        except tk.TclError:
            pass
        if not follow:
            return
        for iid in self.tree_scp.get_children():
            vals = self.tree_scp.item(iid, "values")
            if vals and str(vals[0]) == follow:
                self.tree_scp.selection_set(iid)
                self.tree_scp.see(iid)
                return
        for iid in self.tree_d.get_children():
            vals = self.tree_d.item(iid, "values")
            if vals and str(vals[0]) == follow:
                self.tree_d.selection_set(iid)
                self.tree_d.see(iid)
                return

    def _pick_chat_from_tree(self, tree: ttk.Treeview) -> None:
        sel = tree.selection()
        if not sel:
            return
        vals = tree.item(sel[0], "values")
        if not vals:
            return
        eid = str(vals[0])
        self._map_highlight_eid = eid
        values = self._combo_values_list(self.chat_combo)
        if eid in values:
            self.chat_combo.set(eid)
            self._render_chat_transcript()

    def _render_chat_transcript(self) -> None:
        eid = self._chat_entity_var.get().strip()
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.delete("1.0", tk.END)
        for m in self._chat_messages.get(eid, []):
            who = "You" if m.get("role") == "user" else eid or "Entity"
            self.chat_log.insert(tk.END, f"{who}: {m.get('content', '')}\n\n")
        self.chat_log.see(tk.END)
        self.chat_log.config(state=tk.DISABLED)

    def _clear_active_chat(self) -> None:
        eid = self._chat_entity_var.get().strip()
        if eid:
            self._chat_messages.pop(eid, None)
        self._render_chat_transcript()

    def _send_chat_message(self) -> None:
        if self._chat_busy:
            return
        eid = self._chat_entity_var.get().strip()
        text = self.chat_entry.get().strip()
        if not eid or not text:
            return
        reach = self.store.get_meta().get("ollama_reachable")
        if reach is False:
            self._chat_messages.setdefault(eid, []).append(
                {
                    "role": "assistant",
                    "content": "[Ollama unreachable — start the server or check config base_url.]",
                }
            )
            self._render_chat_transcript()
            return

        self._chat_messages.setdefault(eid, []).append({"role": "user", "content": text})
        self.chat_entry.delete(0, tk.END)
        self._render_chat_transcript()
        self._chat_busy = True
        self.chat_send_btn.configure(state="disabled")
        hist = [dict(x) for x in self._chat_messages[eid]]
        threading.Thread(target=self._chat_worker, args=(eid, hist), daemon=True).start()

    def _chat_worker(self, eid: str, hist: list[dict[str, str]]) -> None:
        try:
            meta = self.store.get_meta()
            tick_raw = meta.get("sim_tick", 0)
            try:
                tick_i = int(tick_raw)
            except (TypeError, ValueError):
                tick_i = 0
            ent = self.store.get_entity(eid)
            pov = pov_snapshot_for_entity(self.store, eid, tick=tick_i)
            system = build_chat_system_prompt(eid, ent, sim_tick=tick_i, pov_snapshot=pov)
            api_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in hist
                if m.get("role") in ("user", "assistant")
            ]
            api_messages = api_messages[-24:]
            tout = min(120.0, float(self.settings.ollama.timeout_seconds))
            reply = ollama_roleplay_chat(
                self.settings.ollama.base_url,
                self.settings.ollama.model,
                system,
                api_messages,
                timeout=tout,
            )
            self.root.after(0, lambda e=eid, r=reply: self._finish_chat_round(e, r, None))
        except Exception as exc:
            self.root.after(0, lambda e=eid, x=str(exc): self._finish_chat_round(e, None, x))

    def _finish_chat_round(self, eid: str, assistant_text: str | None, err: str | None) -> None:
        self._chat_busy = False
        if err:
            self._chat_messages.setdefault(eid, []).append({"role": "assistant", "content": f"[error] {err}"})
        elif assistant_text:
            self._chat_messages.setdefault(eid, []).append({"role": "assistant", "content": assistant_text})
        if self._chat_entity_var.get().strip() == eid:
            self._render_chat_transcript()
        values = self._combo_values_list(self.chat_combo)
        self.chat_send_btn.configure(state="normal" if values and not self._chat_busy else "disabled")

    def _refresh_chat_targets(self) -> None:
        if self._memory and not self._shared_memory_with_sim:
            self.chat_combo.configure(values=[], state="disabled")
            self._chat_entity_var.set("")
            self.chat_send_btn.configure(state="disabled")
            return
        ids: list[str] = []
        for eid in sorted(self.store.list_entity_ids()):
            ent = self.store.get_entity(eid)
            if not ent:
                continue
            if ent.get("kind") == "scp" or (str(eid).startswith("D-") and ent.get("kind") == "d_class"):
                ids.append(eid)
        self.chat_combo.configure(values=ids)
        self.chat_combo.configure(state="readonly" if ids else "disabled")
        cur = self._chat_entity_var.get().strip()
        if cur not in ids:
            if ids:
                self.chat_combo.set(ids[0])
                self._render_chat_transcript()
            else:
                self._chat_entity_var.set("")
        if not self._chat_busy:
            self.chat_send_btn.configure(state="normal" if ids else "disabled")

    def _refresh(self) -> None:
        try:
            self._draw_frame()
        except Exception as exc:
            self.lbl_warn.config(text=f"poll error: {exc}")
        self.root.after(self._poll_ms, self._refresh)

    def _draw_frame(self) -> None:
        if self._memory and not self._shared_memory_with_sim:
            try:
                self._map_legend.pack_forget()
            except tk.TclError:
                pass
            self.lbl_warn.config(
                text="In-memory store — use Redis + second terminal, or run with --live.",
            )
            o_txt, o_fg = _ollama_banner({}, self.settings)
            self.lbl_ollama.config(text=o_txt, fg=o_fg)
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
            self._refresh_chat_targets()
            return

        self.txt_help.pack_forget()
        if not self._map_legend.winfo_ismapped():
            self._map_legend.pack(fill=tk.X, padx=10, pady=(0, 2), before=self._outer)
        self._map_legend.config(text=self._map_legend_full)

        if self._shared_memory_with_sim:
            self.lbl_warn.config(text="Embedded sim — shared memory (no Redis)")
        else:
            self.lbl_warn.config(text="")

        meta = self.store.get_meta()
        o_txt, o_fg = _ollama_banner(meta, self.settings)
        self.lbl_ollama.config(text=o_txt, fg=o_fg)

        tick = meta.get("sim_tick", "—")
        phase = str(meta.get("tick_phase", "") or "").strip()
        phase_s = f" · {phase}" if phase else ""
        self.lbl_tick.config(
            text=f"tick: {tick}{phase_s}  ·  {self.settings.simulation.site_id}",
        )

        graph = room_graph_for_meta(meta)
        rooms_live: dict[str, dict[str, Any]] = self.store.get_rooms() or {}
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
                if not p2:
                    continue
                r_lo, r_hi = (rid, nb) if rid < nb else (nb, rid)
                loss_lo = float(graph.get(r_lo, {}).get("sound_loss_db", 18.0))
                loss_hi = float(graph.get(r_hi, {}).get("sound_loss_db", 18.0))
                lock_into_rid = bool(rooms_live.get(rid, {}).get("is_locked"))
                lock_into_nb = bool(rooms_live.get(nb, {}).get("is_locked"))
                self.canvas.create_line(
                    cx, cy, p2[0], p2[1],
                    fill="#2f3d5c",
                    width=1,
                    tags=("passage",),
                )
                mx = (cx + p2[0]) / 2.0
                my = (cy + p2[1]) / 2.0
                dx = p2[0] - cx
                dy = p2[1] - cy
                ln = math.hypot(dx, dy) or 1.0
                ux, uy = dx / ln, dy / ln
                d_mark = min(16.0, ln * 0.24)
                # Toward rid: sound entering ``rid`` is penalized if ``rid`` is locked (neighbor perspective).
                sx_r = mx - ux * d_mark
                sy_r = my - uy * d_mark
                sx_n = mx + ux * d_mark
                sy_n = my + uy * d_mark
                r_open, r_fill, r_w = ("#4a5568", "#141820", 1) if not lock_into_rid else ("#c98a4a", "#6b3d12", 1)
                n_open, n_fill, n_w = ("#4a5568", "#141820", 1) if not lock_into_nb else ("#c98a4a", "#6b3d12", 1)
                self.canvas.create_oval(
                    sx_r - 4, sy_r - 4, sx_r + 4, sy_r + 4,
                    outline=r_open, fill=r_fill, width=r_w, tags=("passage",),
                )
                self.canvas.create_oval(
                    sx_n - 4, sy_n - 4, sx_n + 4, sy_n + 4,
                    outline=n_open, fill=n_fill, width=n_w, tags=("passage",),
                )
                px, py = -uy, ux
                tdx, tdy = px * 13.0, py * 13.0
                self.canvas.create_text(
                    mx + tdx,
                    my + tdy,
                    text=f"{loss_lo:.0f}·{loss_hi:.0f}",
                    fill="#4d5c78",
                    font=("Helvetica", 6),
                    tags=("passage",),
                )

        for rid, (cx, cy) in centers.items():
            x0, y0 = cx - rw / 2, cy - rh / 2
            x1, y1 = cx + rw / 2, cy + rh / 2
            self._room_rects[rid] = (x0, y0, x1, y1)
            rb = rooms_live.get(rid, {})
            locked_here = bool(rb.get("is_locked"))
            lit = _parse_light_level(rb if rb else None)
            fill_col = _room_fill_for_light(lit)
            outline_col = "#c9a06a" if locked_here else "#3a4a6e"
            outline_w = 2 if locked_here else 1
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline=outline_col,
                fill=fill_col,
                width=outline_w,
                tags=("room", rid),
            )
            short = rid.replace("con-", "C-").replace("site-", "")[:14]
            self.canvas.create_text(cx, cy - rh / 2 - 8, text=short, fill="#8899bb", font=("Helvetica", 8))
            lit_pct = int(round(lit * 100.0))
            self.canvas.create_text(
                cx, cy + rh / 2 - 10,
                text=f"{lit_pct}%",
                fill="#6a7a9a",
                font=("Helvetica", 7),
                tags=("room", rid),
            )
            tags_list = rb.get("tags") if isinstance(rb.get("tags"), list) else []
            tag_hint = ""
            if tags_list:
                t0 = str(tags_list[0])
                if t0 and t0 != "standard":
                    tag_hint = t0[:11]
            if tag_hint:
                self.canvas.create_text(
                    cx, cy + rh / 2 - 2,
                    text=tag_hint,
                    fill="#5a6988",
                    font=("Helvetica", 6),
                    tags=("room", rid),
                )

        entities: dict[str, dict[str, Any]] = {}
        for eid in self.store.list_entity_ids():
            e = self.store.get_entity(eid)
            if e:
                entities[eid] = e

        if self._map_highlight_eid and self._map_highlight_eid not in entities:
            self._map_highlight_eid = None

        tick_active_raw = meta.get("tick_active_agent")
        tick_active: str | None = tick_active_raw if isinstance(tick_active_raw, str) else None

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

            man = self._map_highlight_eid == eid
            act = tick_active is not None and tick_active == eid
            r = 7
            self.canvas.create_oval(
                mx - r,
                my - r,
                mx + r,
                my + r,
                fill=_stable_color(eid),
                outline="#ffe8a0" if man else "#ffffff",
                width=3 if man else 1,
            )
            if act:
                self.canvas.create_oval(
                    mx - r - 5,
                    my - r - 5,
                    mx + r + 5,
                    my + r + 5,
                    outline="#3dd6e0",
                    width=2,
                    dash=(4, 4),
                    fill="",
                )
            if man:
                self.canvas.create_oval(
                    mx - r - 9,
                    my - r - 9,
                    mx + r + 9,
                    my + r + 9,
                    outline="#ffcc33",
                    width=3,
                    fill="",
                )
            label = eid.replace("SCP-", "").replace("____", "..")[:12]
            label_fill = "#fff8e0" if man else "#e0e0e8"
            self.canvas.create_text(
                mx + 12,
                my,
                text=label,
                fill=label_fill,
                anchor="w",
                font=("Helvetica", 9, "bold" if man else "normal"),
            )

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
            man = self._map_highlight_eid == eid
            act = tick_active is not None and tick_active == eid
            self.canvas.create_rectangle(
                mx - rd,
                my - rd,
                mx + rd,
                my + rd,
                fill=fill,
                outline="#ffe8a0" if man else outline,
                width=3 if man else 1,
            )
            if act:
                self.canvas.create_rectangle(
                    mx - rd - 5,
                    my - rd - 5,
                    mx + rd + 5,
                    my + rd + 5,
                    outline="#3dd6e0",
                    width=2,
                    dash=(4, 4),
                    fill="",
                )
            if man:
                self.canvas.create_rectangle(
                    mx - rd - 9,
                    my - rd - 9,
                    mx + rd + 9,
                    my + rd + 9,
                    outline="#ffcc33",
                    width=3,
                    fill="",
                )

        self._roster_repainting = True
        try:
            for tree, rows in ((self.tree_scp, scp_rows), (self.tree_d, d_rows)):
                for iid in tree.get_children():
                    tree.delete(iid)
                for row_vals, tag in rows:
                    eid_cell = str(row_vals[0])
                    row_tags: tuple[str, ...] = (tag,)
                    if tick_active and eid_cell == tick_active:
                        row_tags = (tag, "tick_active")
                    tree.insert("", tk.END, values=row_vals, tags=row_tags)
            self._restore_roster_tree_selection()
        finally:
            self._roster_repainting = False
        self._refresh_chat_targets()
        try:
            self.root.update_idletasks()
        except tk.TclError:
            pass


def run_gui(*, config_path: Path | None = None) -> None:
    settings = load_settings(config_path)
    store = connect_world_state(settings.redis.url, settings.redis.enabled)
    _silence_macos_imk_stderr()
    root = tk.Tk()
    SiteMapApp(root, store, settings)
    root.minsize(1240, 720)
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
    _silence_macos_imk_stderr()
    root = tk.Tk()
    SiteMapApp(root, shared, settings, shared_memory_with_sim=True)
    root.minsize(1240, 720)
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Site-Zero live map (Tkinter + Redis)")
    _pkg_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--config", type=Path, default=_pkg_root / "config.yaml")
    args = parser.parse_args()
    run_gui(config_path=args.config)


if __name__ == "__main__":
    main()
