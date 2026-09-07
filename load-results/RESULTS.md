# k6 load-test evidence

Run date: 1 September 2026

## Test conditions

- Fresh Docker Compose stack: FastAPI, Redis 7, PostgreSQL 16.
- Initial inventory: 1,000 units.
- Rate limit: capacity 10,000, refill 10,000 requests/second, so it did not mask inventory contention.
- k6 scenario: 1,000 virtual users sharing 5,000 unique purchase attempts.
- Duration: 6.02 seconds.

## Measured result

| Measure | Result |
| --- | ---: |
| HTTP throughput | 831.19 requests/second |
| HTTP latency p50 (median) | 711.93 ms |
| HTTP latency p99 | 3,248.95 ms |
| HTTP latency average | 1,143.05 ms |
| Accepted (`202`) | 1,000 (20%) |
| Sold out (`409`) | 4,000 (80%) |
| Rate limited (`429`) | 0 |
| Unexpected status / failed custom check | 0 |
| PostgreSQL reservations | 1,000 distinct IDs |
| Redis remaining stock | 0 |

## Invariant proof

`successful_reservations = 1,000 <= initial_stock = 1,000`.

The k6 script's application-level check passed all 5,000 responses: a `202`, `409`, or `429` is an expected business outcome. k6's built-in `http_req_failed` metric shows 80% because it treats the intentional `409` responses as HTTP failures; it does **not** mean the load test failed. Read the explicit counters above for business success/rejection rates.

The raw k6 data is saved as `k6-summary.json` in this same directory. Re-run on a fresh sale state before comparing results, because a completed run intentionally exhausts stock.

## What this teaches

The test does not prove that the API is low-latency: p99 was about 3.25 seconds under a burst of 1,000 virtual users. It does prove the project’s primary correctness claim under this load: once the thousandth successful Lua reservation occurred, all later requests saw sold-out state instead of receiving additional inventory.
