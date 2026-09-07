Flash-Sale Inventory Reservation
Goal

You are a Staff Backend Engineer and my technical mentor.

Help me build a high-concurrency inventory reservation system proving zero overselling under real load — using:

Python 3.12+
FastAPI
Redis
Redis Lua scripting
PostgreSQL (simple, no queue — direct or lightweight background write)
pytest
k6 or Locust for load testing
Docker Compose

This is a fresher resume project. Let's build the basic, correct version first — Redis Lua for atomicity, no distributed locks, no broker. We can extend into RabbitMQ, Redis Streams, or other infrastructure later, if and when the project actually needs it. If a requirement below would need more infrastructure to be "fully correct" at massive scale, note it as a future improvement in the write-up for now.

I need to understand:
The architecture, the basics of all the concepts (I am new to most of the tech stack)
Why we have designed the file structure like this
How do design a project, a database a backend service etc
why a single Lua script is atomic and why that beats a lock
why Redis is single-threaded and what that buys us here
why the API returns 202 instead of 200
what actually happens if Redis succeeds but the Postgres write fails, and why that's an acceptable, explainable trade-off at this scope
1. Goal / Invariant
1,000 units of stock. Up to several thousand concurrent purchase attempts.
Hard invariant: successful_reservations <= initial_stock, always, provably, under load — not just claimed.
2. Redis Inventory + Lua Script

One Lua script that atomically:

Checks stock exists and is > 0.
Decrements stock.
Generates a reservation ID.
Returns success/failure.

Do NOT use Redlock, SETNX loops, or app-level locking. Explain why Lua execution is inherently atomic in Redis and why that removes the need for a lock entirely.

3. Rate Limiting

Redis-based token bucket limiter in front of the inventory logic. Explain burst capacity, refill rate, and why this needs to live in Redis rather than as an in-process counter (multi-instance correctness).

4. Async Response + Simple Persistence
Successful reservation → 202 Accepted with reservation_id, status, item_id.
After the Lua script succeeds, write the reservation to PostgreSQL (either directly in a background task, or via a very simple in-process queue — no broker). Use a unique constraint on reservation_id so a retry or duplicate write can't create two rows.
Explicitly discuss: what happens if Redis succeeds but the Postgres write fails or the process crashes before it happens? Is the reservation lost? What would you add (e.g. a durable Redis Stream) if this needed to be bulletproof — and why you're not adding it now.
5. Load Testing (your proof point)
k6 or Locust script simulating several thousand concurrent requests against limited stock.
Report actual measured numbers: throughput, p50/p99 latency, success rate, rejection rate, and confirm successful_reservations <= stock from the database after the run.
This test output is your resume evidence — treat it as a deliverable, not an afterthought.
6. Failure Scenarios (keep it to the ones that matter at this scope)
Redis unavailable at request time.
Duplicate reservation request (same client retries).
Process crashes after Redis decrement, before Postgres write.
Redis restarts (stock state — discuss what's lost and how you'd reload initial stock).

For each: what state exists, what's recoverable, what isn't, and why.

7. Learning Mode

Stages:

Requirements and scope justification
Redis data model
Lua script (with a live demo of the race condition it prevents)
Token bucket rate limiter
FastAPI endpoint + 202 pattern
Postgres persistence + idempotent write
Load testing setup and execution
Failure scenario walkthroughs
Docker Compose
Final review

Teach each concept before implementing it, explain the code afterward, and give me a short exercise per stage.

8. Interview Preparation

Give me:

15 likely interviewer questions with strong answers
Tricky ones specifically: "What if Redis decrements but the Postgres write never happens?", "Why not Redlock?", "Why not SELECT FOR UPDATE in Postgres instead?", "How do you prove zero overselling?"
A clear 1-minute and 3-minute explanation of the project
A short section on what you'd add if this had to scale 100x (Redis Streams, a real broker) — to show you understand the boundary of your current design without having over-built it