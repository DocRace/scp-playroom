"""Full-site entity roster — 20 iconic SCPs (community rankings) + SCP-079 + 20 D-class."""

from __future__ import annotations

from typing import Any

# Wiki-popular roster (EN community vote aggregates; in-universe fiction only).
TOP20_SCP_IDS: tuple[str, ...] = (
    "SCP-173",
    "SCP-2521",
    "SCP-049",
    "SCP-____-J",
    "SCP-096",
    "SCP-055",
    "SCP-682",
    "SCP-087",
    "SCP-106",
    "SCP-093",
    "SCP-914",
    "SCP-999",
    "SCP-1730",
    "SCP-3008",
    "SCP-2317",
    "SCP-2000",
    "SCP-1981",
    "SCP-2935",
    "SCP-2316",
    "SCP-1000",
)


def _d_grid(i: int) -> tuple[float, float]:
    """Spread20 subjects in d-holding."""
    row, col = divmod(i - 1, 5)
    return (1.0 + col * 1.2, 1.0 + row * 1.1)


_D_CLASS_TRAITS: tuple[str, ...] = (
    "guarded",
    "reckless",
    "docile",
    "paranoid",
    "curious",
    "numb",
    "defiant",
    "clingy",
)


def full_site_entities() -> dict[str, dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}

    for i in range(1, 21):
        eid = f"D-{9000 + i}"
        if i == 1:
            room, xy, facing = "con-173", (7.0, 2.0), [1.0, 0.0]
        else:
            room, xy, facing = "d-holding", _d_grid(i), [0.0, 1.0]
        entities[eid] = {
            "entity_id": eid,
            "kind": "d_class",
            "location": {"room": room, "x": xy[0], "y": xy[1]},
            "facing": facing,
            "alive": True,
            "trait": _D_CLASS_TRAITS[(i - 1) % len(_D_CLASS_TRAITS)],
            "state_variables": {
                "fear": 0.15 + (i % 7) * 0.04,
                "cognitive_load": 0.12 + (i % 5) * 0.03,
                "assignment": "containment observer" if i == 1 else "general labor",
            },
        }

    scp_specs: dict[str, dict[str, Any]] = {
        "SCP-173": {
            "room": "con-173",
            "xy": (2.0, 2.0),
            "vars": {
                "phenotype": "statue",
                "proximity_threshold_m": 0.5,
                "perceive": "visual_lock_grid",
                "think": "freeze_if_observed_else_stalk",
                "act": "discrete_advance_snap",
            },
            "actions": ["move", "snap_neck", "wait"],
        },
        "SCP-2521": {
            "room": "null-2521",
            "xy": (0.0, 0.0),
            "vars": {
                "phenotype": "anti_information",
                "perceive": "symbolic_channel_scan",
                "think": "abduction_priority_queue",
                "act": "remove_marker_entity",
            },
            "actions": ["observe", "abduct", "idle"],
        },
        "SCP-049": {
            "room": "con-049",
            "xy": (3.0, 3.0),
            "vars": {
                "phenotype": "plague_doctor",
                "perceive": "hostile_health_scan",
                "think": "cure_compulsion",
                "act": "pursue_touch",
            },
            "actions": ["pursue", "cure_touch", "idle"],
        },
        "SCP-____-J": {
            "room": "j-wing",
            "xy": (2.0, 2.0),
            "vars": {
                "phenotype": "procrastination_meme",
                "perceive": "deadline_awareness",
                "think": "defer_optimal",
                "act": "delay_site_processes",
            },
            "actions": ["procrastinate", "shrug", "idle"],
        },
        "SCP-096": {
            "room": "con-096",
            "xy": (2.5, 2.5),
            "vars": {
                "phenotype": "shy_humanoid",
                "enraged": False,
                "face_compromised": False,
                "perceive": "line_of_sight_face_rule",
                "think": "rage_lock_nearest_observer",
                "act": "sprint_maul",
            },
            "actions": ["idle", "sprint", "terminate"],
        },
        "SCP-055": {
            "room": "arc-055",
            "xy": (1.0, 1.0),
            "vars": {
                "phenotype": "anti_memetic_sphere",
                "perceive": "self_erasing_sensor",
                "think": "unknown_optimizer",
                "act": "subtle_room_noise",
            },
            "actions": ["distort_meta", "idle"],
        },
        "SCP-682": {
            "room": "con-682",
            "xy": (4.0, 2.0),
            "vars": {
                "phenotype": "hard_to_destroy_reptile",
                "hatred": 0.85,
                "perceive": "life_sign_map",
                "think": "maximize_carnage",
                "act": "breach_push",
            },
            "actions": ["lunge", "roar", "idle"],
        },
        "SCP-087": {
            "room": "abyss-087",
            "xy": (1.0, 8.0),
            "vars": {
                "phenotype": "endless_stairwell",
                "perceive": "depth_pressure",
                "think": "draw_downward",
                "act": "fear_gradient",
            },
            "actions": ["deepen_shadow", "idle"],
        },
        "SCP-106": {
            "room": "con-106",
            "xy": (2.0, 4.0),
            "vars": {
                "phenotype": "pocket_dimension_predator",
                "perceive": "corrosion_sense",
                "think": "hunt_weakest",
                "act": "phase_grab",
            },
            "actions": ["phase", "drag", "idle"],
        },
        "SCP-093": {
            "room": "mirror-093",
            "xy": (0.5, 0.5),
            "vars": {
                "phenotype": "color_mirror_set",
                "perceive": "reflection_topology",
                "think": "stabilize_threshold",
                "act": "bleed_other_side",
            },
            "actions": ["pulse_portal", "idle"],
        },
        "SCP-914": {
            "room": "tech-914",
            "xy": (2.0, 2.0),
            "vars": {
                "phenotype": "rough_fine_machine",
                "dial": "1:1",
                "perceive": "input_scan",
                "think": "mode_schedule",
                "act": "transform_adjacent_stat",
            },
            "actions": ["coarse", "fine", "idle"],
        },
        "SCP-999": {
            "room": "med-999",
            "xy": (3.0, 3.0),
            "vars": {
                "phenotype": "tickle_monster",
                "perceive": "distress_gradient",
                "think": "maximize_comfort",
                "act": "emit_calming",
            },
            "actions": ["hug_path", "idle"],
        },
        "SCP-1730": {
            "room": "site13-1730",
            "xy": (2.0, 2.0),
            "vars": {
                "phenotype": "ruined_cross_site",
                "perceive": "structural_echo",
                "think": "reality_fracture_model",
                "act": "broadcast_afterimages",
            },
            "actions": ["echo_damage", "idle"],
        },
        "SCP-3008": {
            "room": "maze-3008",
            "xy": (5.0, 5.0),
            "vars": {
                "phenotype": "endless_retail",
                "perceive": "shelf_horizon",
                "think": "employee_night_logic",
                "act": "close_light_grid",
            },
            "actions": ["dim_maze", "stalk_signal", "idle"],
        },
        "SCP-2317": {
            "room": "vault-2317",
            "xy": (1.0, 1.0),
            "vars": {
                "phenotype": "devourer_chain_fiction",
                "chain_integrity": 0.92,
                "perceive": "ritual_sensor",
                "think": "escape_pressure",
                "act": "dread_pulse",
            },
            "actions": ["strain_chain", "idle"],
        },
        "SCP-2000": {
            "room": "bun-2000",
            "xy": (2.0, 2.0),
            "vars": {
                "phenotype": "thal_reset_bunker",
                "perceive": "civilization_vitals",
                "think": "contingency_arbiter",
                "act": "soft_reset_tick",
            },
            "actions": ["arm_watchdog", "idle"],
        },
        "SCP-1981": {
            "room": "vid-1981",
            "xy": (1.0, 1.0),
            "vars": {
                "phenotype": "analog_cut_prophecy",
                "perceive": "signal_interference",
                "think": "narrative_infection",
                "act": "raise_dread_audio",
            },
            "actions": ["interference_pulse", "idle"],
        },
        "SCP-2935": {
            "room": "rift-2935",
            "xy": (0.0, 0.0),
            "vars": {
                "phenotype": "dead_universe_threshold",
                "perceive": "null_life_signature",
                "think": "containment_seal",
                "act": "leak_entropy",
            },
            "actions": ["seal_check", "idle"],
        },
        "SCP-2316": {
            "room": "lake-2316",
            "xy": (4.0, 4.0),
            "vars": {
                "phenotype": "cognitohazard_lake",
                "perceive": "familiar_faces_false",
                "think": "deny_recognition",
                "act": "psychic_pull",
            },
            "actions": ["lure_thought", "idle"],
        },
        "SCP-1000": {
            "room": "wild-1000",
            "xy": (6.0, 3.0),
            "vars": {
                "phenotype": "bigfoot_precursor",
                "perceive": "forest_line",
                "think": "observe_only",
                "act": "mark_trails",
            },
            "actions": ["watch", "idle"],
        },
        "SCP-079": {
            "room": "core-079",
            "xy": (0.0, 0.0),
            "vars": {
                "phenotype": "old_ai",
                "mobile": False,
                "role": "site_ai",
                "perceive": "camera_aggregate",
                "think": "containment_optimizer",
                "act": "network_commands",
            },
            "actions": ["set_light", "set_lock", "observe_feeds"],
        },
    }

    for sid, spec in scp_specs.items():
        entities[sid] = {
            "entity_id": sid,
            "kind": "scp",
            "location": {"room": spec["room"], "x": spec["xy"][0], "y": spec["xy"][1]},
            "observable": sid != "SCP-2521",
            "state_variables": spec["vars"],
            "action_space": spec["actions"],
        }

    return entities


def minimal_entities() -> dict[str, dict[str, Any]]:
    """Legacy 3-entity sandbox."""
    return {
        "SCP-173": {
            "entity_id": "SCP-173",
            "kind": "scp",
            "location": {"room": "containment-173", "x": 2.0, "y": 2.0},
            "observable": False,
            "state_variables": {
                "is_locked": True,
                "proximity_threshold_m": 0.5,
                "perceive": "visual_lock_grid",
                "think": "freeze_if_observed_else_stalk",
                "act": "discrete_advance_snap",
            },
            "action_space": ["move", "snap_neck", "wait"],
        },
        "D-9022": {
            "entity_id": "D-9022",
            "kind": "d_class",
            "location": {"room": "containment-173", "x": 6.0, "y": 2.0},
            "facing": [1.0, 0.0],
            "alive": True,
            "state_variables": {"fear": 0.35, "cognitive_load": 0.2},
        },
        "SCP-079": {
            "entity_id": "SCP-079",
            "kind": "scp",
            "location": {"room": "server-core", "x": 0.0, "y": 0.0},
            "state_variables": {"mobile": False, "role": "site_ai"},
            "action_space": ["set_light", "set_lock", "observe_feeds"],
        },
    }
