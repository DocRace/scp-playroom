"""Shared SCP-079 LLM instructions — tick planner and GUI operator chat."""

# Models often emit a single tool call; these lines explicitly permit large ``actions`` arrays.
SCP079_BATCH_TOOL_POLICY = (
    "BATCHING: In one JSON response, the \"actions\" array may list MANY tool objects. "
    "When policy or the operator implies several rooms, emit one tool call per room_id in the same array—"
    "do not collapse to a single room. Example: if three corridors need locks, include three "
    "set_room_lock objects. If site-wide dimming is required, include one set_room_light per room key "
    "from the snapshot (dozens of entries is valid). "
    "Use only room_id values that exist in the provided rooms map.\n"
)
