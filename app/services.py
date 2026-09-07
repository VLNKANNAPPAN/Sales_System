import logging

from redis.asyncio import Redis
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.database import SessionLocal
from app.lua import RESERVE_STOCK, TOKEN_BUCKET
from app.models import Reservation

logger = logging.getLogger(__name__)


def stock_key(item_id: str) -> str:
    return f"inventory:{{{item_id}}}:stock"


async def initialize_inventory(redis: Redis) -> None:
    # NX prevents a restarting API instance from resetting live stock.
    await redis.set(stock_key(settings.item_id), settings.initial_stock, nx=True)


async def allow_request(redis: Redis, client_key: str) -> bool:
    result = await redis.eval(
        TOKEN_BUCKET, 1, f"rate-limit:{client_key}", settings.rate_limit_capacity,
        settings.rate_limit_refill_per_second, 60_000,
    )
    return int(result[0]) == 1


async def reserve(redis: Redis, item_id: str, idempotency_key: str) -> tuple[int, str | None]:
    result = await redis.eval(
        RESERVE_STOCK, 3, stock_key(item_id), f"inventory:{{{item_id}}}:sequence",
        f"inventory:{{{item_id}}}:idempotency:{idempotency_key}", "resv_", 86_400,
    )
    return int(result[0]), (result[1].decode() if isinstance(result[1], bytes) else result[1] or None)


async def persist_reservation(reservation_id: str, item_id: str, idempotency_key: str) -> None:
    """Best-effort persistence. Redis is the source of reservation truth in this MVP."""
    try:
        async with SessionLocal() as session:
            statement = insert(Reservation).values(
                reservation_id=reservation_id, item_id=item_id,
                idempotency_key=idempotency_key, status="reserved",
            ).on_conflict_do_nothing(index_elements=[Reservation.reservation_id])
            await session.execute(statement)
            await session.commit()
    except Exception:
        logger.exception("Reservation %s was accepted but not persisted", reservation_id)
