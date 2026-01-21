# Pytest fixtures for FreedomVPN bot testing
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database.models import Base, User, Subscription, Payment, SubscriptionStatus, PaymentStatus


# ============== ASYNC EVENT LOOP ==============
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============== IN-MEMORY DATABASE ==============
@pytest.fixture
async def test_engine():
    """Create in-memory SQLite engine for testing"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False}
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create async session for testing"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


# ============== TEST USERS ==============
@pytest.fixture
async def test_user(test_session):
    """Create a test user in database"""
    user = User(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User",
        referral_code="TEST123",
        balance=0.0
    )
    test_session.add(user)
    await test_session.flush()
    return user


@pytest.fixture
async def test_admin(test_session):
    """Create a test admin user"""
    admin = User(
        telegram_id=987654321,
        username="admin",
        first_name="Admin",
        is_admin=True
    )
    test_session.add(admin)
    await test_session.flush()
    return admin


# ============== MOCK MARZBAN SERVICE ==============
@pytest.fixture
def mock_marzban():
    """Mock MarzbanService for testing without real API calls"""
    # Patch where marzban_service is imported/used, not where it's defined
    with patch("services.subscription_service.marzban_service") as mock:
        # Mock create_user response
        mock.create_user = AsyncMock(return_value={
            "username": "FreedomVPN_test_abc1",
            "subscription_url": "https://marzban.example.com/sub/test123",
            "status": "active",
            "expire": int((datetime.now() + timedelta(hours=72)).timestamp()),
            "used_traffic": 0,
            "data_limit": 0
        })
        
        # Mock get_user response
        mock.get_user = AsyncMock(return_value={
            "username": "FreedomVPN_test_abc1",
            "status": "active",
            "expire": int((datetime.now() + timedelta(hours=72)).timestamp()),
            "used_traffic": 1024 * 1024 * 100,  # 100 MB
            "subscription_url": "https://marzban.example.com/sub/test123"
        })
        
        # Mock extend_user response
        mock.extend_user = AsyncMock(return_value={
            "username": "FreedomVPN_test_abc1",
            "status": "active",
            "expire": int((datetime.now() + timedelta(days=30)).timestamp())
        })
        
        # Mock delete_user response
        mock.delete_user = AsyncMock(return_value=True)
        
        # Mock get_all_users response
        mock.get_all_users = AsyncMock(return_value=[
            {"username": "FreedomVPN_user1", "used_traffic": 1024**3, "status": "active"},
            {"username": "FreedomVPN_user2", "used_traffic": 512*1024**2, "status": "active"},
        ])
        
        # Mock get_subscription_url
        mock.get_subscription_url = AsyncMock(return_value="https://marzban.example.com/sub/test123")
        
        # Mock get_user_links
        mock.get_user_links = AsyncMock(return_value={
            "subscription_url": "https://marzban.example.com/sub/test123",
            "links": ["vless://..."],
            "expire": int((datetime.now() + timedelta(hours=72)).timestamp()),
            "status": "active",
            "used_traffic": 0,
            "data_limit": 0
        })
        
        # Static method
        mock.generate_username = MagicMock(return_value="FreedomVPN_test_abc1")
        mock.calculate_expire_timestamp = MagicMock(
            return_value=int((datetime.now() + timedelta(hours=72)).timestamp())
        )
        
        yield mock


# ============== SUBSCRIPTIONS ==============
@pytest.fixture
async def test_subscription(test_session, test_user):
    """Create a test subscription"""
    subscription = Subscription(
        telegram_id=test_user.telegram_id,
        user_id=test_user.telegram_id,
        marzban_username="FreedomVPN_test_abc1",
        subscription_url="https://marzban.example.com/sub/test123",
        plan_type="trial",
        status=SubscriptionStatus.ACTIVE,
        expires_at=datetime.utcnow() + timedelta(hours=72)
    )
    test_session.add(subscription)
    await test_session.flush()
    return subscription


@pytest.fixture
async def expired_subscription(test_session, test_user):
    """Create an expired subscription"""
    subscription = Subscription(
        telegram_id=test_user.telegram_id + 1,  # Different user
        user_id=test_user.telegram_id + 1,
        marzban_username="FreedomVPN_expired_xyz9",
        subscription_url="https://marzban.example.com/sub/expired",
        plan_type="week",
        status=SubscriptionStatus.ACTIVE,
        expires_at=datetime.utcnow() - timedelta(days=1)  # Expired yesterday
    )
    test_session.add(subscription)
    await test_session.flush()
    return subscription


# ============== PAYMENTS ==============
@pytest.fixture
async def test_payment(test_session, test_user):
    """Create a test payment"""
    payment = Payment(
        telegram_id=test_user.telegram_id,
        yukassa_payment_id="test-payment-123",
        amount=199.0,
        plan_type="month",
        status=PaymentStatus.SUCCEEDED
    )
    test_session.add(payment)
    await test_session.flush()
    return payment
