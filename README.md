# Flash-Sale Inventory Reservation

This project demonstrates a narrow but valuable invariant: **successful reservations never exceed available inventory**, even when many requests race at once.

## Run it

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Reserve stock:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8001/v1/items/flash-sale-item/reservations -Headers @{"Idempotency-Key"="demo-1"}
```

4. Load test after raising the demo rate-limit values in `.env` (otherwise rate limiting deliberately dominates): `docker run --rm --network project_2_default -v "${PWD}:/work" grafana/k6 run /work/load/k6-reservations.js`. The raw report is saved under `load-results/`.

For the first Docker-backed concurrency check without installing k6, run `python scripts/concurrency_check.py`. See `docs/live-verification.md` for the commands, observed results, and how to interpret them.

See `docs/failure-scenarios.md` for the Redis outage, retry, crash-gap, and restart walkthroughs.

## Architecture

`Client -> Redis token bucket -> Redis Lua reserve -> 202 response -> background PostgreSQL insert`

Redis is the live inventory authority. The reservation Lua script runs to completion before Redis executes another command, so checking and decrementing stock cannot interleave with another buyer. No Redlock or app-level lock is needed: the script itself is the atomic critical section.

`202 Accepted` means the reservation has been accepted by Redis, while its PostgreSQL audit row is intentionally written after the response. A `200` would more strongly imply all requested processing is complete.

## Important trade-off

If Redis accepts a reservation and the process crashes before its PostgreSQL insert, stock remains decremented but the audit row can be missing. This MVP prefers never overselling over perfect audit durability. The error is logged; an operational reconciliation can compare Redis reservations with PostgreSQL. A production-grade next step is appending the reservation to a durable Redis Stream inside the same Lua script and consuming it reliably, or using a durable transactional design.

Redis restart behavior depends on persistence. Compose enables AOF, but an unrecoverable Redis data loss loses the live stock state; re-initialize from a trusted inventory source only when a sale is inactive, or restore from a durable event log in a fuller design.

## Project structure

- `app/lua.py` — the two atomic Redis scripts.
- `app/services.py` — Redis operations and idempotent persistence.
- `app/main.py` — HTTP boundary and `202` workflow.
- `app/models.py` — minimal PostgreSQL reservation audit schema.
- `load/` — k6 evidence script.
- `tests/` — fast script contract checks; add Docker-backed integration tests next.

## Proof procedure

Run the k6 script, save its output in `load-results/`, then query PostgreSQL:

```sql
SELECT count(*) AS successful_reservations FROM reservations;
```

It must be `<= INITIAL_STOCK` (1,000 by default). Record k6 throughput, p50/p99 latency, and counts of `202`, `409`, and `429` in `load-results/RESULTS.md`. Measured numbers are intentionally not invented; run this on your machine to create your resume evidence.

## Learning exercise: stage 1

Before proceeding, explain why a Python `GET stock`, followed by `if stock > 0`, followed by `DECR` is unsafe when two requests run concurrently. Then compare that sequence with the single Lua script.
