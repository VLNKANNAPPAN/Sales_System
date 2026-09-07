# Architecture and learning guide

## Stage 1 — requirements and scope

There are 1,000 units and many buyers. The only non-negotiable rule is that a successful reservation cannot exceed 1,000. The system accepts a narrow trade-off: it protects inventory synchronously in Redis and records an audit row later in PostgreSQL. It does not yet promise a durable audit record after every crash.

Exercise: write down the difference between “never oversell” and “never lose an audit event.” They are separate guarantees.

## Stage 2 — Redis data model and Lua

For one item, Redis stores `inventory:{item}:stock`, `inventory:{item}:sequence`, and one idempotency key per client request. Curly braces make the keys share a Redis Cluster hash slot, which keeps the script valid if Redis Cluster is added later.

Redis processes commands serially on its event loop. When Lua starts, Redis does not run a different client's command until the script returns. `GET`, conditional check, `DECR`, ID generation, and idempotency record therefore form one indivisible transition. Two normal application commands could interleave; this one script cannot. A distributed lock would add lock acquisition, expiry, and failure modes while protecting code that is already atomic, so it is unnecessary here.

Exercise: sketch the bad interleaving when stock is 1 and two application servers both run `GET` then `DECR` as separate commands.

## Stage 3 — token bucket

A bucket starts with `capacity` tokens: that is the permitted burst. Tokens refill continuously at `refill_per_second`. Each request removes one; a request with no token gets `429`. The bucket lives in Redis because multiple API containers need to observe and update the same counter. An in-memory Python counter would give each container its own allowance.

Exercise: with capacity 10 and refill rate 2/s, calculate how many requests can succeed immediately and after waiting 3 seconds.

## Stage 4 — HTTP and persistence

`POST /v1/items/{item_id}/reservations` first rate limits, then reserves in Lua. On success it responds `202 Accepted` with the Redis reservation ID and schedules a PostgreSQL insert. `202` says accepted for processing; it correctly avoids claiming that the asynchronous audit insert has finished. Pass the same `Idempotency-Key` on a retry: Redis returns the original reservation ID without decrementing again. PostgreSQL also has unique constraints as a second line of defence for writes.

Exercise: send the same curl/PowerShell request twice with the same `Idempotency-Key` and compare IDs.

## Stage 5 — failure boundaries

| Scenario | Current behavior | Recovery / next design |
| --- | --- | --- |
| Redis unavailable | Request fails; no inventory decision is made. | Alert and retry after Redis recovers. |
| Duplicate client retry | Same key returns the same reservation; no extra decrement. | Keep idempotency TTL appropriate for the client retry window. |
| Crash after Lua, before PostgreSQL | Stock is protected, but the database audit row may be missing. | Atomically append to Redis Stream in Lua, then use a durable consumer. |
| Redis restart/data loss | Live stock and idempotency keys may be lost unless persistence restores them. | AOF, backup, and rehydrate only from a trusted durable sale ledger. |

The final two rows are why this is a correct zero-oversell demo, not a fully durable order system.

## Stage 6 — prove it under load

Run k6 with more unique requests than stock. The k6 script treats `202` as accepted, `409` as sold out, and `429` as rate-limited. Use unique `X-Client-ID` values solely for the demo so one shared IP bucket does not hide the inventory contention. After the run, count PostgreSQL rows and preserve the raw k6 output in `load-results/RESULTS.md`. Do not write made-up performance figures.

Exercise: run twice without resetting stock. Explain why the second run should not create more accepted reservations.
