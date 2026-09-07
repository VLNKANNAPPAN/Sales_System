from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.database import engine
from app.models import Base
from app.services import allow_request, initialize_inventory, persist_reservation, reserve


class ReservationResponse(BaseModel):
    reservation_id: str
    status: str = "reserved"
    item_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(settings.redis_url, decode_responses=False)
    app.state.redis = redis
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await initialize_inventory(redis)
    yield
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title="Flash Sale Inventory", lifespan=lifespan)


@app.post("/v1/items/{item_id}/reservations", response_model=ReservationResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_reservation(
    item_id: str, request: Request, background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    client_id: str | None = Header(default=None, alias="X-Client-ID"),
) -> ReservationResponse:
    # In production this must come from authenticated user identity, not a caller-controlled header.
    client_key = client_id or (request.client.host if request.client else "unknown")
    try:
        if not await allow_request(request.app.state.redis, client_key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        key = idempotency_key or str(uuid4())
        outcome, reservation_id = await reserve(request.app.state.redis, item_id, key)
    except RedisError as error:
        # Failing closed protects the inventory invariant: never guess stock without Redis.
        raise HTTPException(status_code=503, detail="Inventory service unavailable") from error
    if outcome == 0:
        raise HTTPException(status_code=409, detail="Item is sold out")
    if outcome == 1:
        background_tasks.add_task(persist_reservation, reservation_id, item_id, key)
    return ReservationResponse(reservation_id=reservation_id, item_id=item_id)


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    await request.app.state.redis.ping()
    return {"status": "ok"}
