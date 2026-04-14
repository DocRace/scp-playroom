# scp-playroom

Experimental **multi-agent containment simulation** (“Site-Zero”): rule-based and optional LLM-driven agents, Redis-backed world state, and a small live map GUI.

**Fiction only** — simplified mechanics for a local lab toy, not canon SCP Foundation material.

## Repository layout

| Path | Description |
| ----------- | ------------------------------------------------ |
| `site-zero` | Python package `site_zero`, CLI, `config.yaml`   |

## Requirements

- **Python** 3.11+
- **Redis** (Redis Stack JSON recommended) — required for the live map and normal multi-process runs  
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
| `--gui`         | Open Tkinter live map (needs Redis + running sim)    |
| `--site minimal`| Small 173 sandbox instead of full site               |

Examples:

```bash
python -m site_zero --rules-only --ticks 100
python -m site_zero --gui                    # second terminal, while sim runs
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
- **Live map** (`--gui`): polls Redis for entity positions and last action lines written each tick.

## License / attribution

SCP-inspired themes are used under community norms for transformative fan works; this repo is an independent coding exercise, not endorsed by SCP Wiki staff.
