import json
from collections.abc import Mapping
from datetime import timedelta
from typing import Final

from pydantic import JsonValue, TypeAdapter, ValidationError

from litellm.redis.transport.contract import Delete, Get, RedisFailure, Set

KEY_PREFIX: Final = "litellm:polling:response:"

_DOCUMENT: Final = TypeAdapter(str)
_STATE: Final = TypeAdapter(dict[str, JsonValue])


def state_key(polling_id: str) -> str:
    return f"{KEY_PREFIX}{polling_id}"


def put(polling_id: str, state: Mapping[str, object], *, ttl: timedelta) -> Set:
    return Set(state_key(polling_id), json.dumps(json.dumps(state)), ttl=ttl)


def get(polling_id: str) -> Get:
    return Get(state_key(polling_id))


def delete(polling_id: str) -> Delete:
    return Delete(state_key(polling_id))


def decode(raw: bytes | None | RedisFailure) -> dict[str, JsonValue] | None | RedisFailure:
    if raw is None or isinstance(raw, RedisFailure):
        return raw
    try:
        return _STATE.validate_json(_DOCUMENT.validate_json(raw))
    except ValidationError as e:
        return RedisFailure(kind="decode", message=f"polling state is not a JSON object: {e}")
