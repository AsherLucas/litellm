---
name: redis-access
description: Add Redis operations, move raw redis-py clients, scripts or keyspaces behind RedisTransport and stores in litellm/redis, without porting them to Rust or expanding migration scope
---

# Redis access

Python reaches Redis through `RedisTransport` (`litellm/redis/transport/contract.py`), and each keyspace lives in a store under `litellm/redis/stores/`. Callers get typed results from a store and keep policy (limits, fail open or closed, retries, logging)

Read the reference for the task

- `references/transport.md` for adding a command, the failure kinds, the namespace and TTL rules, and moving raw `init_async_client` / `async_register_script` / `.redis_client` access onto the transport
- `references/store.md` for adding coordination state, moving a keyspace into a store, store tests, and the Rust port plan

Rules that always apply

- New code never calls `init_async_client`, `init_pubsub_client`, `async_register_script` or `.redis_client`, and never imports redis-py outside `litellm/redis/transport/redis_py.py`
- New coordination state gets a store, not a new `RedisCache` method, and a Python store doesn't need a Rust port
- Keys and values in Redis are a wire format shared with older pods and Rust. A move keeps them byte for byte
- A `transport` failure on a write is an unknown outcome, never "not applied"
- Do only what was asked. An extraction isn't a store move, and a store move isn't a Rust port. Confirm before any Rust work
