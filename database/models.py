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

    # Referral system
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    referral_code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    total_referrals: Mapped[int] = mapped_column(Integer, default=0)
    total_earned: Mapped[float] = mapped_column(Float, default=0.0)

    # Notifications
    notify_expiration: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_referrals: Mapped[bool] = mapped_column(Boolean, default=True)

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

class Promocode(Base):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    # Discount details
    discount_type: Mapped[str] = mapped_column(String(20))  # percent, fixed, bonus_days
    discount_value: Mapped[float] = mapped_column(Float)  # процент скидки, сумма или количество дней

    # Usage limits
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited
    current_uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Plan restrictions
    applicable_plans: Mapped[str | None] = mapped_column(String(255), nullable=True)  # comma-separated: "day,week,month"

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromocodeUsage(Base):
    __tablename__ = "promocode_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promocode_id: Mapped[int] = mapped_column(Integer, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    payment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    discount_amount: Mapped[float] = mapped_column(Float)
    used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReferralTransaction(Base):
    __tablename__ = "referral_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Who gets the bonus
    referred_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Who made the payment
    payment_id: Mapped[int] = mapped_column(Integer, index=True)

    amount: Mapped[float] = mapped_column(Float)  # Bonus amount
    percentage: Mapped[float] = mapped_column(Float)  # Percentage of payment (e.g., 30.0 for 30%)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
