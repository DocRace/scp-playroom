# scp-playroom

Research sandbox for multi-agent world simulation.

**Fiction only** — a coding playground for studying emergent behavior of LLM-anchored agent societies. Not canon for any of the fictional universes it draws from.

---

## What's here

The repo contains **two independent projects**:

### 1. `living-world/` — current focus
Stage A MVP of the main project: a no-player, auto-running virtual world simulator.
Three worldviews run simultaneously: SCP Foundation · Cthulhu Mythos · Liaozhai Zhiyi.

**Start here:**
```bash
cd living-world
./lw
```

See [`living-world/README.md`](living-world/README.md) for full details.

### 2. `site-zero/` — legacy
Earlier single-pack SCP-Foundation prototype with Tkinter map GUI, Ollama + Redis backend.
Superseded by `living-world/` but kept as reference.

```bash
cd site-zero
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m site_zero              # requires Redis + Ollama
```

See `site-zero/README.md` for details (Tcl/Tk required for map).

---

## Design documents

High-level product / architecture / roadmap docs live in `docs/` (gitignored; team-only):

- `docs/product-direction.md` — Stage A → D roadmap, three-world rationale
- `docs/architecture.md` — system design, tier routing, data flow
- `docs/stat-machine-design.md` — importance scoring, tier 1/2/3 policy
- `docs/next-steps.md` — non-blocking work streams
- `docs/tech-glossary.md` — terminology reference
- `docs/flow-loops.md` — tick + event flow diagrams
- `docs/mvp-roadmap.md` — feature sequencing
- `docs/lbs-infrastructure.md` — mobile/LBS deployment notes (future)

---

## Philosophy

- **Content is data, engine is code.** YAML packs define worlds; Python runs them.
- **LLMs are optional flavor.** Pure rule-based Tier 1 simulation runs indefinitely at zero token cost; higher tiers light up narrative at moments of importance.
- **Physical logic before narrative logic.** An SCP-173 unobserved in a room with a D-class WILL produce a fatality — mechanically, not because a storyteller chose to.
- **Emergent stories, not scripted ones.** Storytellers propose candidates; stat machines resolve them; you discover what happened by reading the Chronicle.

---

## License

MIT for all code. Content packs follow their source licenses (see per-pack notes in `living-world/world_packs/`).
