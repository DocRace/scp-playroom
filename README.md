# scp-playroom

Experimental **multi-agent containment simulation** (“Site-Zero”): rule-based and optional LLM-driven agents, Redis-backed world state, and a small live map GUI.

**Fiction only** — simplified mechanics for a local lab toy, not canon SCP Foundation material.

## Repository layout

| Path | Description |
| ----------- | ------------------------------------------------ |
| `site-zero` | Python package `site_zero`, CLI, `config.yaml`   |

## Requirements

- **Python** 3.11+
- **Redis** (Redis Stack JSON recommended) — for `--gui` while the sim runs in another terminal  
- **Tcl/Tk** — required for `--gui` / `--live` (see **Troubleshooting** if `No module named '_tkinter'`)  
- **Ollama** (optional) — LLM policies for SCP-079, D-class, SCP-173; rules-only mode works without it

## Quick start

```bash
cd site-zero
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### Redis (Docker)

```bash
cd site-zero
docker compose up -d
```

Default URL matches `config.yaml`: `redis://localhost:6379/0`.

### Run the simulation

From `site-zero` (with Redis up and `redis.enabled: true` in `config.yaml`):

```bash
python -m site_zero
```

Useful flags:

| Flag            | Purpose |
| --------------- | ---------------------------------------------------- |
| `--ticks N`     | Stop after N ticks                                   |
| `--memory`      | In-process store only (no Redis) — **GUI won’t sync** |
| `--rules-only`  | No Ollama; deterministic rules                       |
| `--narrative`   | Ollama one-line narrative per tick (slow)            |
| `--gui`         | Open Tkinter live map (needs Redis + running sim)    |
| `--live`        | Sim + map in one process (shared memory; no Redis)   |
| `--site minimal`| Small 173 sandbox instead of full site               |

Examples:

```bash
python -m site_zero --rules-only --ticks 100
python -m site_zero --live                   # sim + map; needs Tcl/Tk (see below)
python -m site_zero --gui                    # second terminal, while sim runs (Redis)
```

### Configuration

Edit `site-zero/config.yaml`, or override with environment variables, for example:

- `SITE_ZERO_REDIS_URL`, `SITE_ZERO_REDIS_ENABLED`
- `OLLAMA_BASE_URL`, `SITE_ZERO_MODEL`
- `SITE_ZERO_SITE_PRESET` — `full` or `minimal`
- `SITE_ZERO_AGENT_LLM` — enable/disable agent LLM calls

## What it simulates (high level)

- **Full preset**: hub-and-spoke site graph, many rooms, a roster of iconic SCP-style entities with simple per-tick rules, ~20 D-class subjects, SCP-079 site controls, SCP-173 with line-of-sight physics.
- **Minimal preset**: legacy two-room style sandbox for SCP-173.
- **Live map** (`--live` or `--gui` + Redis): positions; SCP/D-class roster with a **Lit** column (current room `light_level` as %); optional **entity chat** when Ollama is up; and **room / passage** overlays — room **tile + bottom light bar** reflect `light_level`, amber outline when `is_locked`, room **tags** when not generic, and on each edge markers + a **dB pair** aligned with the acoustic graph (see the in-window legend). Locks change noise propagation, not movement, in this build.

## Troubleshooting

### `ModuleNotFoundError: No module named '_tkinter'`

Homebrew’s `python@3.13` often ships without Tk. Install the matching `python-tk` formula and **recreate the venv** with that interpreter, for example:

```bash
brew install python-tk@3.13
cd site-zero
rm -rf .venv
"$(brew --prefix python@3.13)/bin/python3.13" -m venv .venv
source .venv/bin/activate
pip install -e .
python -m site_zero --live
```

Alternatively use the installer from [python.org](https://www.python.org/downloads/), which includes Tk.

## License / attribution

SCP-inspired themes are used under community norms for transformative fan works; this repo is an independent coding exercise, not endorsed by SCP Wiki staff.
