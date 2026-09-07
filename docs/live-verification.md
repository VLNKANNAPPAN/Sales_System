# Live verification: the first four steps

This is the practical companion to the architecture guide. It records a real local run on 1 September 2026; it is not an estimated benchmark.

## 1. Start the three services

The project was started with `docker compose up --build -d`. Redis and PostgreSQL passed their health checks. Another local process already occupied host port 8000, so this project's Docker mapping uses **http://localhost:8001**. The FastAPI process remains on port 8000 inside its container.

Why this matters: Docker Compose gives the API its real dependencies instead of replacing Redis or PostgreSQL with mocks. We are testing the actual Lua engine and PostgreSQL uniqueness constraints.

## 2. Send a request, then retry it

Both requests used exactly the same headers:

```powershell
$headers = @{ "Idempotency-Key" = "learning-retry-1"; "X-Client-ID" = "learning-client" }
Invoke-RestMethod -Method Post -Uri http://localhost:8001/v1/items/flash-sale-item/reservations -Headers $headers
```

Observed responses: `resv_1`, then `resv_1` again.

The `Idempotency-Key` identifies one purchase attempt. On the second call, the Lua script finds its Redis mapping before it looks at stock and returns the original reservation. A new key means a new attempt; reuse a key only when retrying the same attempt.

## 3. Verify one decrement, not two

After the two calls, Redis reported stock `999`, not `998`:

```powershell
docker compose exec -T redis redis-cli GET 'inventory:{flash-sale-item}:stock'
```

That is the important idempotency property: response retries are safe even when the first response might have been lost by the client.

## 4. Run a concurrent, Docker-backed check

The live check sent **1,005 unique concurrent attempts** through the running API, after the first reservation had consumed one unit. Its observed HTTP result was:

```json
{"202": 999, "409": 6}
```

The resulting PostgreSQL query was:

```text
reservations=1000, distinct_ids=1000
```

Redis stock was `0`. Therefore `successful_reservations = 1000 <= initial_stock = 1000`: the no-oversell invariant held when requests outnumbered inventory.

Repeat this check from a fresh sale state with the reusable script:

```powershell
python scripts/concurrency_check.py --requests 1005 --workers 150 --max-success 1000
docker compose exec -T postgres psql -U flashsale -d flashsale -Atc "SELECT count(*) FROM reservations;"
```

The script makes HTTP requests from your host to Dockerized dependencies; it uses only Python's standard library. It verifies that `202` responses do not exceed the supplied stock bound. The database query is the independent audit check.

For a fully fresh run, use a fresh Docker volume or reset sale data using a deliberately designed admin/reset workflow. Do not reset stock while a sale is active: that would invalidate the test and could create duplicate availability.

## What we have proved—and what we have not

We proved the concurrency invariant for this implementation and run: Redis's one atomic Lua operation did not accept more than the stock. The k6 stage is also complete; see `load-results/RESULTS.md` for measured throughput, p50/p99 latency, and database evidence.
