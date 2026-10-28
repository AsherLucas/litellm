# Redis stores

A store owns one keyspace. Read this before adding coordination state, moving a keyspace out of its caller, or porting a store to Rust

## Why stores

Keys, encoding, TTLs and reply decoding for each keyspace are spread across Python modules today, and Rust already has a second response-cache key builder in `cache_response::cache_key`. Python and Rust pods share one Redis, so if their keys or values differ they silently split counters, cooldowns or locks. Each shared keyspace needs one definition of its data and one set of operations, and the store is that definition

## Shape

`litellm/redis/stores/response_polling.py` is the reference

- One module per keyspace in `litellm/redis/stores/<keyspace>.py`
- Sans-IO. A store is plain functions, it never takes or imports a transport, builds a client, reads settings or imports `RedisCache`
- It owns, and nothing outside it knows
  - the key builder (`state_key`), with logical keys and no namespace
  - the value codec
  - expiry, always taken from the caller and put on the command
  - reply decoding into typed results
- An operation is a function that returns one command from `transport/contract.py` (`Get`, `Set`, `Delete`), plus a `decode` that turns the reply into a typed result. `decode` also accepts the `RedisFailure` so a caller can chain `decode(await transport.execute(get(...)))`
- A value that doesn't decode is a `decode` failure, never a miss or a default
- No logging, no retries, no fallback. Those are policy

## Callers

`ResponsePollingHandler` in `litellm/proxy/response_polling/polling_handler.py` is the reference caller

- Run the store's command on `redis_cache.transport()` and `match` the result, ending in `assert_never` when the result has more than two cases
- Keep policy in the caller: which TTL applies, fail open or closed, and the `with_service_target` that labels its commands. The transport already logs failures and emits service events
- A caller never builds a key or touches a client. Exposing the key builder for an existing public helper (`get_cache_key`) is fine as a delegate

## Adding new coordination state

Add a store, not a new `RedisCache` method. A Python store is the finished state for now, and adding one does not require a Rust port

## Moving an existing keyspace into a store

- Move the key builders, codec, TTLs and decoding verbatim. Keep policy in the caller
- Keys and values already in Redis are a wire format. Old and new pods read each other's writes during a rolling deploy
  - polling state was written by `async_set_cache`, which runs `json.dumps` on a value that was already JSON text, so the store encodes with `json.dumps(json.dumps(state))` and decodes both layers
  - changing a key or codec is its own change with a migration plan, never part of a move
- Move one keyspace per change

Keyspaces still in their callers, as candidates (paths under `litellm/`, not exhaustive)

- response cache, `caching/caching.py`
- rate limit windows, `proxy/hooks/parallel_request_limiter_v3.py`
- deployment cooldowns, `router_utils/cooldown_cache.py`
- routing affinity, `caching/affinity_cache.py`
- login throttle, `proxy/auth/login_throttle.py`
- session caps, `proxy/hooks/max_budget_per_session_limiter.py` and `max_iterations_limiter.py`
- enqueued batch tokens, `proxy/hooks/batch_enqueued_tokens.py`

Response cache identity (normalization, hashing into a logical key) is backend-independent and is not store logic. The store only maps that logical key to storage. Reuse or move `cache_response::cache_key`, never write a third key builder

## Tests

- Test the store through its caller against `fake_redis_cache(server)` from `tests/_support/fake_redis.py`. That is a real `RedisCache` on a `fakeredis.FakeServer`, so namespace, breaker and failure mapping are the production ones
- Cover each result the caller acts on, that the TTL lands (`pttl` on a raw `FakeAsyncRedis`), and an outage (`server.connected = False`)
- When a keyspace moves, seed with the old `RedisCache` writer and read back with the old reader, so old and new pods read each other's writes. See `_seed` and `_legacy_read` in `tests/unit/proxy/response_polling/test_response_polling_handler.py`
- Assert returned values and Redis state, never the commands sent

## Porting a store to Rust

Rust stores are sans-IO. Confirm with the user before starting the first port, since the bridge for it doesn't exist yet

- `litellm-rust/crates/redis-store` gets one module per keyspace. An operation is a pure function that builds a plan and a pure function that decodes the reply into a typed result. Its `AGENTS.md` has the crate rules
- A plan is the same tagged union as the Python commands (`Get`, `Set`, `Delete`), with logical keys and explicit TTL
- A `#[pyclass]` per store in `litellm-rust/crates/python-bridge/src/redis/` exposes the plan builders and decoders as sync methods. It never does IO and never holds a transport
- The Python store in `litellm/redis/stores/` keeps its signatures and delegates to the pyclass, so callers keep running the same commands on their `RedisTransport`. The transport behind it can be redis-py or the native client, the store doesn't change
- Results come back as Pydantic models generated from the Rust types, frozen, so callers keep matching on the same classes. A decode error maps to `RedisFailure(kind="decode")`
- Rust callers run the same plans on `litellm-redis-client`, so there is one implementation per operation
- Rust never awaits the Python transport. That would cross the boundary on every command and leave the Rust gateway without a store
- The codec has to write the exact bytes Python writes. Pod lock owners are `json.dumps` output, which escapes non-ASCII, and `serde_json` doesn't, so a Rust pod couldn't release a lock a Python pod took
- Each move ships old/new compatibility tests against one Redis, covering keys, values, expiry and atomicity through a rolling deploy
