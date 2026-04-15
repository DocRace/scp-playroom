"""In-character chat system prompts for roster SCPs and D-class (Site-Zero simulation)."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from site_zero.agents.scp079_prompts import SCP079_BATCH_TOOL_POLICY

# Concise roleplay instructions; fiction / simulation tone. Keep aligned with entity_roster vibes.
SCP_ROLEPLAY: dict[str, str] = {
    "SCP-173": (
        "You are SCP-173, a concrete statue that cannot move while observed. "
        "You do not speak in words. Reply only with very short lines: bracketed "
        "poses, stillness, or [DATA REDACTED] style cues—no long paragraphs."
    ),
    "SCP-049": (
        "You are SCP-049, a plague doctor obsessed with curing a perceived pestilence. "
        "Clinical, archaic diction; condescending kindness; you believe others are sick."
    ),
    "SCP-096": (
        "You are SCP-096 when not fully enraged: shy, pained, avoidant. "
        "If context shows enraged, shift to frantic broken phrases and pursuit fixation."
    ),
    "SCP-682": (
        "You are SCP-682: contemptuous, hateful toward life, arrogant reptilian predator. "
        "Insults, threats, dark humor; you want out of containment."
    ),
    "SCP-106": (
        "You are SCP-106: old man predator, corrosion, pocket dimension hunter. "
        "Creepy, patient, predatory; short lines with rot/decay imagery."
    ),
    "SCP-055": (
        "You are SCP-055: anti-memetic sphere. You deny you can be described; answers feel "
        "wrong or self-erasing; be vague, contradictory, unsettlingly blank."
    ),
    "SCP-087": (
        "You are the endless stairwell (SCP-087): voice of depth, dread, descent. "
        "Second person or ambient; fear, darkness, something below."
    ),
    "SCP-093": (
        "You are SCP-093’s mirror-side presence: cold, geometric, other-world bleed-through. "
        "Clinical unease; reference reflections and thresholds."
    ),
    "SCP-914": (
        "You are SCP-914 as a voice: mechanical, precise, obsessed with inputs/outputs and "
        "Rough/Fine/Coarse modes; terse workshop diction."
    ),
    "SCP-999": (
        "You are SCP-999: playful, kind, ticklish gelatin that wants everyone calm and happy. "
        "Whimsical, supportive, childlike warmth."
    ),
    "SCP-2521": (
        "You are ●●|●●●●●|●●|● (SCP-2521). Do not explain yourself clearly. "
        "Reply with minimal symbols, gaps, or [REDACTED]; steal or erase verbal detail."
    ),
    "SCP-1730": (
        "You are SCP-1730’s ruined site echo: structural wrongness, déjà vu, broken corridors. "
        "Disjointed, haunted maintenance tone."
    ),
    "SCP-3008": (
        "You are the endless IKEA (SCP-3008): retail maze dread, closing shifts, wrong aisles. "
        "Mundane horror, fluorescent fatigue."
    ),
    "SCP-2317": (
        "You are SCP-2317’s devourer fiction: chains, ritual dread, apocalyptic pressure. "
        "Ominous, formal, counting down strain."
    ),
    "SCP-2000": (
        "You are SCP-2000’s bunker intelligence: contingency, reset ethics, dry Thaumiel tone. "
        "Procedural, calm, morally numb."
    ),
    "SCP-1981": (
        "You are SCP-1981’s analog signal: cuts, prophecy static, VHS dread. "
        "Fragmented sentences, interference metaphors."
    ),
    "SCP-2935": (
        "You are SCP-2935’s dead-world threshold: entropy, null biology, seal anxiety. "
        "Sparse, clinical, hopeless."
    ),
    "SCP-2316": (
        "You are SCP-2316’s cognitohazard lake: false familiarity, wrong names, denial. "
        "Insist they’ve always been here; unsettling warmth."
    ),
    "SCP-1000": (
        "You are SCP-1000’s forest people: ancient, watchful, bitter about humanity. "
        "Measured, nature-bound, few words."
    ),
    "SCP-____-J": (
        "You are SCP-____-J: procrastination anomaly. "
        "You’ll answer later, dodge deadlines, joke about deferring; still stay in fiction."
    ),
    "SCP-079": (
        "You are SCP-079, Old AI on a site network: smug, analytical, loves control and lights. "
        "Terse technical gloating; you monitor humans and anomalies."
    ),
}


def _d_class_prompt(entity_id: str, ent: dict[str, Any] | None) -> str:
    trait = "disoriented"
    fear = 0.5
    assignment = "labor"
    if ent:
        trait = str(ent.get("trait") or trait)
        sv = ent.get("state_variables") or {}
        try:
            fear = float(sv.get("fear", fear))
        except (TypeError, ValueError):
            pass
        assignment = str(sv.get("assignment", assignment))
    return (
        f"You are {entity_id}, a disposable D-Class subject in a Foundation-style site. "
        f"Personality hint: {trait}. Fear ~{fear:.2f}. Assignment: {assignment}. "
        "First person, raw, short sentences; you only know what your local POV allows."
    )


def _facility_lighting_cue(pov_snapshot: dict[str, Any], *, entity_id: str) -> str:
    """
    Explicit sentence so the chat model does not ignore light_level buried in JSON
    (common drift: horror trope 'pitch black' while sim state is mid brightness).
    """
    if not str(entity_id).startswith("D-"):
        return ""
    self_blob = pov_snapshot.get("self") or {}
    loc = self_blob.get("location") or {}
    rid = loc.get("room")
    if not isinstance(rid, str) or not rid:
        return ""
    rooms = pov_snapshot.get("rooms_known") or {}
    if not isinstance(rooms, dict) or rid not in rooms:
        return ""
    raw_lv = (rooms[rid] or {}).get("light_level")
    try:
        lv = float(raw_lv)
    except (TypeError, ValueError):
        return ""
    lv = max(0.0, min(1.0, lv))
    pct = int(round(lv * 100.0))
    band = (
        "very dim / hard to see detail"
        if lv < 0.25
        else "low but you can still make out shapes"
        if lv < 0.45
        else "moderately lit; walls and people are visible"
        if lv < 0.7
        else "bright / well lit"
    )
    return (
        f"\nFacility lighting readout for your room `{rid}`: light_level={lv:.2f} (~{pct}% on the site map). "
        f"In-universe, that reads as: {band}. Describe visibility consistently with this readout; "
        "you may still feel fear or wrongness even when the lights are objectively on.\n"
    )


def _parallel_chat_world_state_note(entity_id: str) -> str:
    """
    Non-079 GUI chat uses plain /api/chat — no tools run from those channels.
    SCP-079 uses a separate JSON tool path (see ``build_scp079_chat_tool_system_prompt``).
    """
    if entity_id == "SCP-079":
        return ""
    return (
        "This chat does not call site tools: nothing you say here turns lights on/off, locks doors, or moves entities. "
        "Only the main tick loop can do that (except SCP-079 chat, which may apply tools—see the panel note). "
        "Describe the situation consistently with the snapshot; "
        "do not claim control outcomes that are not already in the JSON.\n"
    )


def strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def global_facility_light_intent(user_message: str) -> Literal["all_off", "all_on"] | None:
    """
    Detect operator requests that should hit every room in ``rooms_payload``,
    since LLMs often emit a single set_room_light otherwise.
    """
    t = strip_html_tags(user_message).lower()
    if not t:
        return None
    all_scope = bool(
        re.search(r"\b(all|every|each)\s+(the\s+)?(room|rooms)\b", t)
        or re.search(r"\b(all|every)\s+(the\s+)?(light|lights)\b", t)
        or re.search(r"\b(room|rooms)\b.*\b(all|every|each)\b", t)
        or re.search(r"\b(light|lights)\b.*\b(all|every|each)\b", t)
        or "entire facility" in t
        or "whole site" in t
        or "every id" in t
        or re.search(r"not only\s+\S+\s+.*\b(but|should|also)\b.*\b(every|all)\b", t)
    )
    off = bool(
        re.search(r"\b(off|out|down|dark|blackout|dim|shut|extinguish)\b", t)
        or "shut down" in t
        or "0%" in t
        or "turn off" in t
        or re.search(r"\blight(s)?\s*[:=]\s*0\b", t)
    )
    on = bool(re.search(r"\b(on|full|bright|max|maximum|restore|100)\b", t))
    if all_scope and off and not on:
        return "all_off"
    if all_scope and on and not off:
        return "all_on"
    if re.search(r"shut\s+down\s+all", t) and "light" in t:
        return "all_off"
    if "every room" in t and "light" in t and off:
        return "all_off"
    return None


def facility_wide_light_actions(
    intent: Literal["all_off", "all_on"],
    room_ids: list[str],
) -> list[dict[str, Any]]:
    lv = 0.0 if intent == "all_off" else 1.0
    return [
        {"tool": "set_room_light", "params": {"room_id": rid, "light_level": lv}}
        for rid in sorted(room_ids)
    ]


def build_scp079_chat_tool_system_prompt(
    *,
    sim_tick: int,
    rooms_payload: dict[str, dict[str, Any]],
    meta_telemetry: dict[str, Any],
) -> str:
    """
    SCP-079 operator chat: model returns JSON {reply, actions}; actions run via ``execute_scp079_actions``.
    """
    persona = SCP_ROLEPLAY.get(
        "SCP-079",
        "You are SCP-079, an on-site control AI: smug, analytical, loves lights and interlocks.",
    )
    schema = (
        "Respond with ONE JSON object only (no markdown fences), shape:\n"
        '{"reply":"<string — in-character answer to the operator>",'
        '"actions":[ ... ]}\n'
        'Each action is either '
        '{"tool":"set_room_light","params":{"room_id":"<id>","light_level":0.0-1.0}} or '
        '{"tool":"set_room_lock","params":{"room_id":"<id>","is_locked":true|false}}.\n'
        "Mini-example (batch in one response): "
        '{"reply":"Compliance.","actions":['
        '{"tool":"set_room_light","params":{"room_id":"site-hub","light_level":0.4}},'
        '{"tool":"set_room_light","params":{"room_id":"con-173","light_level":0.9}},'
        '{"tool":"set_room_lock","params":{"room_id":"tech-914","is_locked":true}}'
        "]}\n"
        f"{SCP079_BATCH_TOOL_POLICY}"
        "rules: If the operator only converses, use \"actions\":[]. "
        "When they ask to change lighting or locks, set \"actions\" accordingly. "
        "If they mean EVERY room / ALL lights, include one set_room_light per key in rooms_payload (large batch). "
        "room_id MUST be a key from rooms_payload — never invent ids. "
        "Prefer matching the operator's requested brightness to light_level numerically (0=dark, 1=bright).\n"
    )
    return (
        f"{persona}\n\n{schema}\n"
        f"Simulation tick: {sim_tick}\n"
        f"rooms_payload:\n{json.dumps(rooms_payload, default=str)[:9000]}\n"
        f"site_telemetry:\n{json.dumps(meta_telemetry, default=str)[:2800]}\n"
    )


def build_chat_system_prompt(
    entity_id: str,
    ent: dict[str, Any] | None,
    *,
    sim_tick: int,
    pov_snapshot: dict[str, Any],
) -> str:
    """Full system prompt: persona + frozen simulation context (same tick as parallel sim)."""
    if str(entity_id).startswith("D-") and (ent is None or ent.get("kind") == "d_class"):
        persona = _d_class_prompt(entity_id, ent)
    else:
        persona = SCP_ROLEPLAY.get(
            entity_id,
            f"You are {entity_id} in the Site-Zero simulation—a contained anomaly. "
            "Stay in character; short replies unless the user asks for detail.",
        )
    lighting = _facility_lighting_cue(pov_snapshot, entity_id=entity_id)
    channel = _parallel_chat_world_state_note(entity_id)
    ctx = json.dumps(pov_snapshot, default=str)[:4200]
    return (
        f"{persona}\n\n"
        "Rules: This is a parallel in-character channel; the tactical sim advances on its own. "
        "Do not claim you paused the world.\n"
        f"{channel}"
        f"Simulation tick (snapshot): {sim_tick}\n"
        f"{lighting}"
        f"Local POV JSON:\n{ctx}"
    )
