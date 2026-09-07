# Interview preparation

## One-minute explanation

I built a FastAPI flash-sale reservation service where Redis is the synchronous inventory authority. Each purchase calls one Redis Lua script that checks stock, decrements it, creates a reservation ID, and records idempotency in one atomic operation. Because Redis does not interleave commands while Lua runs, concurrent buyers cannot both consume the final unit. The API returns `202 Accepted` immediately, then writes an idempotent audit record to PostgreSQL in the background. I load-test with more requests than stock and verify the database count never exceeds initial inventory.

## Three-minute explanation

The key requirement was zero overselling under high contention, so I separated inventory correctness from audit persistence. Redis holds a per-item stock key. A Lua script first checks whether the client retry key already maps to a reservation; if it does, it returns that ID. Otherwise it checks the stock, decrements exactly once, increments a sequence for a readable reservation ID, and stores the idempotency mapping. Redis executes the script atomically, so the check and decrement cannot race.

Ahead of it, a Redis token bucket allows a configurable burst and refill rate across every API instance. That is shared state, which is why it cannot be an in-process counter. After Redis accepts, FastAPI returns `202`, reflecting that PostgreSQL persistence is asynchronous. PostgreSQL uses unique keys to make persistence idempotent.

The explicit limitation is a crash between Redis success and the database insert: stock stays decremented, but the audit row can be absent. That is acceptable for this scoped project because the primary invariant is protected and the gap is observable. At higher stakes I would write to a Redis Stream in the same script and consume it durably, or use another durable transactional outbox design. I demonstrate the main claim with k6 and a post-run count that is never greater than initial stock.

## Likely questions

1. **How do you prove zero overselling?** The only success path decrements stock in one atomic Lua script; the script refuses non-positive stock. Load tests issue more attempts than stock and the persisted accepted count is checked against initial stock.
2. **Why is Lua atomic in Redis?** Redis runs the script without processing another command in the middle, so its multiple reads and writes behave as one transition.
3. **Why not Redlock?** There is no cross-resource critical section to lock. Lua already atomically changes the one Redis inventory state; a distributed lock adds failure complexity without improving this operation.
4. **Why not `SELECT FOR UPDATE` in PostgreSQL?** It can work, but hot inventory rows cause database lock contention and synchronous transactions. Redis Lua is purpose-built for this fast in-memory counter; PostgreSQL remains the audit store here.
5. **What if Redis decrements but PostgreSQL never writes?** The reservation is real in Redis and stock stays protected, but the audit row can be missing. A durable Redis Stream written in the same script is the next improvement.
6. **Why return 202?** The synchronous reservation decision is complete, but the audit write is intentionally background processing.
7. **What does idempotency prevent?** A retry with the same key gets the first reservation ID and cannot consume another unit.
8. **Why use Redis TIME in the limiter?** API hosts may have clock skew; Redis TIME gives the shared bucket one time source.
9. **What is burst capacity?** The number of immediately available token-bucket requests before refilling is needed.
10. **Why must limiting be in Redis?** Multiple API replicas need one shared counter and atomic updates.
11. **What happens when Redis is down?** The service cannot safely reserve, so it fails the request rather than risking an incorrect decision.
12. **Can a Lua script run forever?** It must stay short and bounded; long scripts block Redis, so this script only performs a few constant-time operations.
13. **How does Redis restart affect stock?** Without restored persistence, live inventory and idempotency state disappear; this needs AOF/backups and controlled rehydration.
14. **Why does PostgreSQL have unique constraints too?** They make repeated background writes harmless and protect the audit table independently.
15. **What would you add at 100x?** Redis Cluster, a durable Redis Stream or broker, a reliable consumer, monitoring, reconciliation, and a real durable inventory/order model.
