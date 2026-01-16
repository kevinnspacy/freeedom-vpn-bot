from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from enum import Enum


class Base(DeclarativeBase):
    pass


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Marzban (VLESS + Reality)
    marzban_username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    subscription_url: Mapped[str] = mapped_column(String(500))

    # Subscription details
    plan_type: Mapped[str] = mapped_column(String(50))  # trial, day, week, month, year
    status: Mapped[str] = mapped_column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Payment details
    yukassa_payment_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")

    plan_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)

    # Metadata
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confirmation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
