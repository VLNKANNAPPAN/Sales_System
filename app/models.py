from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(100), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
