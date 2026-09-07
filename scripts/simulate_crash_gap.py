"""Create the documented Redis-success/PostgreSQL-missing gap for local learning only.

Run inside the API container. It calls the exact reservation Lua script but deliberately
does not call persist_reservation(), which models a process crash in that short interval.
"""

import asyncio

from redis.asyncio import Redis

from app.services import reserve


async def main() -> None:
    redis = Redis.from_url("redis://redis:6379/0", decode_responses=False)
    try:
        outcome, reservation_id = await reserve(redis, "flash-sale-item", "crash-gap-demo")
        print(f"Lua outcome={outcome}, reservation_id={reservation_id}")
        print("Persistence deliberately skipped. Query PostgreSQL to observe the missing audit row.")
    finally:
        await redis.aclose()


asyncio.run(main())
