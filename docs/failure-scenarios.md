# Failure scenarios: what the system guarantees

This stage teaches a crucial engineering habit: describe failure behavior precisely. “It handles failures” is not useful; identify the state that was committed, the state that was not, and the recovery path.

## 1. Redis is unavailable at request time

The endpoint now returns `503 Service Unavailable` if its rate-limit or reservation Redis operation fails. It fails **closed**: it does not guess that stock exists and it does not write a reservation directly to PostgreSQL.

Why: continuing without Redis would break the one authority that protects the stock invariant. The client may retry after Redis recovers, using the same idempotency key.

Exercise: stop Redis with `docker compose stop redis`, make one request, observe `503`, then run `docker compose start redis` and retry it.

## 2. The client retries a reservation

State after first request: Redis has less stock, a reservation sequence value, and an idempotency-key-to-reservation-ID mapping. PostgreSQL eventually has one audit row.

State after retry with the same key: Lua returns the existing reservation ID before it checks stock. There is no second decrement and the PostgreSQL primary key makes a repeated write harmless.

Recoverability: complete; the retry itself is safe. The idempotency key must be retained long enough for the expected client retry window.

## 3. Process crashes after Redis success, before PostgreSQL persistence

The Lua script already decremented Redis stock and created the reservation ID. If the process dies before its background task runs, the PostgreSQL audit row is missing. The inventory is not oversold, but the audit trail is incomplete.

This project deliberately accepts that gap to keep the first version small and focus on the zero-oversell invariant. It is observable by reconciliation, but it cannot be recovered perfectly from the PostgreSQL table alone.

At a higher durability level, the Lua script would also append an event to a durable Redis Stream. A consumer would persist that event with retries and a dead-letter/reconciliation process. That makes the event durable at the same point as the stock decrement without introducing a full broker for this beginner project.

Exercise: run `docker compose exec -T api python scripts/simulate_crash_gap.py`, then query the database. The script intentionally stops after Lua to demonstrate the gap without actually killing Docker.

## 4. Redis restarts

Compose starts Redis with AOF enabled. A normal **restart** preserves the container's current filesystem, so its AOF reloads the stock and idempotency keys. A container replacement or an unrecoverable Redis-volume loss does not have that guarantee in this Compose setup.

State after a normal restart: stock can be restored from AOF. State after data loss: live stock and idempotency keys are gone, and blindly reapplying `INITIAL_STOCK` during an active sale could oversell.

Recovery: only rehydrate from a trusted durable source (an event log or authoritative order/inventory database), and only under a controlled sale-recovery procedure. The API’s `SET ... NX` initialization is intentionally safe for restarting an API while Redis remains available; it is not a complete disaster-recovery system.

## Decision table

| Failure | Inventory state | PostgreSQL state | Correct immediate action |
| --- | --- | --- | --- |
| Redis unreachable | No new decrement | No new row | Return `503`; retry later. |
| Duplicate request | One decrement only | One row eventually | Return original reservation ID. |
| Crash after Lua | Decrement committed | Row may be absent | Reconcile; add durable stream for production. |
| Redis data loss | May be unknown/lost | Existing rows may remain | Stop sale and rehydrate from trusted data. |

## Observed local demonstration — 1 September 2026

These are measured results from the Docker stack, not hypothetical output.

| Experiment | Observed result | What it proves |
| --- | --- | --- |
| Stop Redis, then POST reservation | `503`; `/health` returned `ok` after restart | The API fails closed rather than making an unsafe inventory decision. |
| Run `simulate_crash_gap.py` | Lua returned `resv_1`; PostgreSQL count `0`; Redis stock `999` | A Redis reservation can exist without its background audit row if the process dies in that gap. |
| Restart Redis after the simulated gap | Redis stock remained `999` | The normal container restart reloaded current AOF-backed state. |
| POST twice with `Idempotency-Key: duplicate-demo` | Both replies were `resv_2`; PostgreSQL count `1`; Redis stock `998` | A retry receives its original ID and does not decrement stock twice. |

The gap simulation intentionally leaves `resv_1` out of PostgreSQL. That is expected and is a visible reminder that this basic version guarantees inventory safety, not fully durable reservation-event persistence.
