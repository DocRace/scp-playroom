"""World state: Redis JSON (Stack) or in-process memory — entities, rooms, site meta."""

from __future__ import annotations

import json
import threading
import uuid
from abc import ABC, abstractmethod
from typing import Any

try:
    import redis
    from redis.commands.json.path import Path
except ImportError:  # pragma: no cover
    redis = None  # type: ignore
    Path = None  # type: ignore


ENTITY_INDEX_KEY = "sz:entities"
ROOMS_KEY = "sz:site:rooms"
META_KEY = "sz:site:meta"


class WorldStateStore(ABC):
    @abstractmethod
    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def set_entity(self, entity_id: str, data: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def delete_entity(self, entity_id: str) -> None:
        pass

    @abstractmethod
    def list_entity_ids(self) -> list[str]:
        pass

    @abstractmethod
    def publish(self, channel: str, message: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_rooms(self) -> dict[str, dict[str, Any]]:
        """Room id -> { is_locked: bool, light_level: float 0..1, ... }"""
        pass

    @abstractmethod
    def update_room(self, room_id: str, patch: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def replace_rooms(self, rooms: dict[str, dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def get_meta(self) -> dict[str, Any]:
        """Cross-tick site metadata (e.g. last_noise_by_room)."""
        pass

    @abstractmethod
    def set_meta(self, meta: dict[str, Any]) -> None:
        """Replace site meta blob."""
        pass


class MemoryWorldState(WorldStateStore):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entities: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._rooms: dict[str, dict[str, Any]] = {}
        self._meta: dict[str, Any] = {}

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        with self._lock:
            e = self._entities.get(entity_id)
            return json.loads(json.dumps(e)) if e else None

    def set_entity(self, entity_id: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._entities[entity_id] = json.loads(json.dumps(data))

    def delete_entity(self, entity_id: str) -> None:
        with self._lock:
            self._entities.pop(entity_id, None)

    def list_entity_ids(self) -> list[str]:
        with self._lock:
            return list(self._entities.keys())

    def publish(self, channel: str, message: dict[str, Any]) -> None:
        with self._lock:
            self._events.append({"channel": channel, "message": message})

    def drain_events(self) -> list[dict[str, Any]]:
        with self._lock:
            out = self._events[:]
            self._events.clear()
            return out

    def get_rooms(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._rooms))

    def update_room(self, room_id: str, patch: dict[str, Any]) -> None:
        with self._lock:
            cur = dict(self._rooms.get(room_id, {}))
            cur.update(patch)
            self._rooms[room_id] = cur

    def replace_rooms(self, rooms: dict[str, dict[str, Any]]) -> None:
        with self._lock:
            self._rooms = json.loads(json.dumps(rooms))

    def get_meta(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._meta))

    def set_meta(self, meta: dict[str, Any]) -> None:
        with self._lock:
            self._meta = json.loads(json.dumps(meta))


class RedisWorldState(WorldStateStore):
    """Requires Redis Stack (RedisJSON + Pub/Sub)."""

    def __init__(self, url: str) -> None:
        if redis is None:
            raise RuntimeError("redis package is not installed")
        self._r = redis.Redis.from_url(url, decode_responses=True)
        self._json = self._r.json()

    def ping(self) -> None:
        self._r.ping()

    def _entity_key(self, entity_id: str) -> str:
        return f"sz:entity:{entity_id}"

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        key = self._entity_key(entity_id)
        if not self._r.exists(key):
            return None
        return self._json.get(key)  # type: ignore[no-any-return]

    def set_entity(self, entity_id: str, data: dict[str, Any]) -> None:
        key = self._entity_key(entity_id)
        self._json.set(key, Path.root_path(), data)  # type: ignore[arg-type]
        self._r.sadd(ENTITY_INDEX_KEY, entity_id)

    def delete_entity(self, entity_id: str) -> None:
        key = self._entity_key(entity_id)
        self._r.delete(key)
        self._r.srem(ENTITY_INDEX_KEY, entity_id)

    def list_entity_ids(self) -> list[str]:
        ids = self._r.smembers(ENTITY_INDEX_KEY)
        if ids:
            return sorted(ids)
        keys = self._r.keys("sz:entity:*")
        return sorted(k.split(":")[-1] for k in keys)

    def publish(self, channel: str, message: dict[str, Any]) -> None:
        self._r.publish(channel, json.dumps(message))

    def get_rooms(self) -> dict[str, dict[str, Any]]:
        if not self._r.exists(ROOMS_KEY):
            return {}
        return self._json.get(ROOMS_KEY)  # type: ignore[no-any-return]

    def update_room(self, room_id: str, patch: dict[str, Any]) -> None:
        rooms = self.get_rooms()
        cur = dict(rooms.get(room_id, {}))
        cur.update(patch)
        rooms[room_id] = cur
        self._json.set(ROOMS_KEY, Path.root_path(), rooms)  # type: ignore[arg-type]

    def replace_rooms(self, rooms: dict[str, dict[str, Any]]) -> None:
        self._json.set(ROOMS_KEY, Path.root_path(), rooms)  # type: ignore[arg-type]

    def get_meta(self) -> dict[str, Any]:
        if not self._r.exists(META_KEY):
            return {}
        return self._json.get(META_KEY)  # type: ignore[no-any-return]

    def set_meta(self, meta: dict[str, Any]) -> None:
        self._json.set(META_KEY, Path.root_path(), meta)  # type: ignore[arg-type]


def reset_redis_world_state(redis_url: str) -> None:
    """Clear the Redis logical database used by Site-Zero (FLUSHDB on URL's DB index)."""
    if redis is None:
        raise RuntimeError("redis package is not installed")
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    r.ping()
    r.flushdb()


def connect_world_state(redis_url: str, use_redis: bool) -> WorldStateStore:
    if not use_redis:
        return MemoryWorldState()
    try:
        rs = RedisWorldState(redis_url)
        rs.ping()
        return rs
    except Exception:
        return MemoryWorldState()


def new_event_id() -> str:
    return str(uuid.uuid4())
