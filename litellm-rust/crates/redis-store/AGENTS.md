- Sans-IO Redis domain operations shared by the Rust gateway and Python. One module per keyspace (rate limit windows, cooldowns, pod locks, ...), and each owns its key layout, value codec, expiry, Lua and reply decoding
- No IO and no runtime dependency on a Redis client. An operation is a pure function that builds a plan (keys, args, and a command or Lua source) plus a pure function that decodes the reply into a typed result. Never add `redis-client`, `redis`, a connection or an async fn to `[dependencies]`
- Executing a plan belongs to the caller. Rust runs it on `litellm-redis-client`, which applies the namespace and breaker. Python runs it on its `RedisTransport`, whichever backend (redis-py or the native client) was picked at construction. So a keyspace can switch to these definitions before the transport swap is done
- Keys in a plan are logical, without the namespace. The transport adds it once
- Callers keep policy, like which limit applies and whether to fail open on an error. The decoder only maps a reply to a result, and a reply that doesn't decode is an error, never a miss or a default count
- Python and Rust pods share one Redis, so a key, value format, TTL or Lua change splits counters or cooldowns between them during a rolling deploy. Treat every byte a plan writes as a wire format that unmigrated Python paths also read
- One implementation per operation. Response-cache identity (normalization, hashing into a logical key) lives in a backend-independent crate. This crate only maps that logical key to storage, with prefixes and cluster hash tags. Reuse or move `cache-response`'s key builder, never write a third
- Lua is a `&'static str` constant next to the operation that runs it, and declares every key it touches in KEYS, since an undeclared key breaks on cluster depending on slot ownership
- Plan and result types are plain data, since they cross into Python through `crates/python-bridge/src/redis/` and back the generated Pydantic models in `litellm/redis/stores/`

## Tests
- Execute plans against real Redis from `litellm-redis-testing` through `litellm-redis-client`, on each topology through `#[values(Topology::Standalone, Topology::Cluster)]`. Never assert command bytes or a mocked wire
- Assert decoded results, TTLs and atomicity through the store's own operations and Redis state
- When a keyspace moves, add compatibility tests against one Redis that read the Python path's writes and the reverse, so keys, values and expiry hold through a rolling deploy
