# Tests for SubscriptionService
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from services.subscription_service import SubscriptionService
from database.models import Subscription, SubscriptionStatus


class TestSubscriptionService:
    """Test suite for SubscriptionService"""

    @pytest.fixture
    def service(self):
        return SubscriptionService()

    # ============== EXPIRY DATE CALCULATION ==============
    
    def test_calculate_expiry_trial(self, service):
        """Trial should be 72 hours from now"""
        result = service.calculate_expiry_date("trial")
        expected = datetime.utcnow() + timedelta(hours=72)
        
        # Allow 1 minute tolerance
        assert abs((result - expected).total_seconds()) < 60

    def test_calculate_expiry_day(self, service):
        """Day plan should be 1 day from now"""
        result = service.calculate_expiry_date("day")
        expected = datetime.utcnow() + timedelta(days=1)
        
        assert abs((result - expected).total_seconds()) < 60

    def test_calculate_expiry_week(self, service):
        """Week plan should be 7 days from now"""
        result = service.calculate_expiry_date("week")
        expected = datetime.utcnow() + timedelta(weeks=1)
        
        assert abs((result - expected).total_seconds()) < 60

    def test_calculate_expiry_month(self, service):
        """Month plan should be 30 days from now"""
        result = service.calculate_expiry_date("month")
        expected = datetime.utcnow() + timedelta(days=30)
        
        assert abs((result - expected).total_seconds()) < 60

    def test_calculate_expiry_year(self, service):
        """Year plan should be 365 days from now"""
        result = service.calculate_expiry_date("year")
        expected = datetime.utcnow() + timedelta(days=365)
        
        assert abs((result - expected).total_seconds()) < 60

    def test_calculate_expiry_invalid(self, service):
        """Invalid plan type should raise ValueError"""
        with pytest.raises(ValueError, match="Unknown plan type"):
            service.calculate_expiry_date("invalid_plan")

    # ============== CREATE SUBSCRIPTION ==============

    @pytest.mark.asyncio
    async def test_create_subscription_trial(self, service, test_session, test_user, mock_marzban):
        """Successfully create trial subscription"""
        subscription = await service.create_subscription(
            session=test_session,
            telegram_id=test_user.telegram_id,
            plan_type="trial",
            first_name="Test"
        )

        assert subscription is not None
        assert subscription.plan_type == "trial"
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.marzban_username == "FreedomVPN_test_abc1"
        assert subscription.subscription_url is not None

        # Verify Marzban was called
        mock_marzban.create_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subscription_month(self, service, test_session, test_user, mock_marzban):
        """Successfully create month subscription"""
        subscription = await service.create_subscription(
            session=test_session,
            telegram_id=test_user.telegram_id,
            plan_type="month",
            first_name="Test"
        )

        assert subscription.plan_type == "month"
        assert subscription.status == SubscriptionStatus.ACTIVE

    # ============== GET ACTIVE SUBSCRIPTION ==============

    @pytest.mark.asyncio
    async def test_get_active_subscription_exists(self, service, test_session, test_subscription):
        """Get active subscription when it exists"""
        result = await service.get_active_subscription(
            session=test_session,
            telegram_id=test_subscription.telegram_id
        )

        assert result is not None
        assert result.id == test_subscription.id
        assert result.status == SubscriptionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_active_subscription_not_exists(self, service, test_session):
        """Return None when no active subscription"""
        result = await service.get_active_subscription(
            session=test_session,
            telegram_id=999999999  # Non-existent user
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_subscription_expired(self, service, test_session, expired_subscription):
        """Expired subscription should not be returned as active"""
        result = await service.get_active_subscription(
            session=test_session,
            telegram_id=expired_subscription.telegram_id
        )

        assert result is None

    # ============== TRIAL USAGE CHECK ==============

    @pytest.mark.asyncio
    async def test_has_used_trial_yes(self, service, test_session, test_subscription):
        """Return True if user has used trial"""
        result = await service.has_used_trial(
            session=test_session,
            telegram_id=test_subscription.telegram_id
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_has_used_trial_no(self, service, test_session, test_user):
        """Return False if user has not used trial"""
        # test_user has no subscription yet
        result = await service.has_used_trial(
            session=test_session,
            telegram_id=test_user.telegram_id
        )

        assert result is False

    # ============== EXTEND SUBSCRIPTION ==============

    @pytest.mark.asyncio
    async def test_extend_subscription_active(self, service, test_session, test_subscription, mock_marzban):
        """Extend active subscription - should add time"""
        original_expires = test_subscription.expires_at

        result = await service.extend_subscription(
            session=test_session,
            subscription=test_subscription,
            plan_type="month",
            first_name="Test"
        )

        assert result.expires_at > original_expires
        assert result.status == SubscriptionStatus.ACTIVE
        mock_marzban.extend_user.assert_called_once()

    @pytest.mark.asyncio 
    async def test_extend_subscription_expired(self, service, test_session, expired_subscription, mock_marzban):
        """Extend expired subscription - should start from now"""
        result = await service.extend_subscription(
            session=test_session,
            subscription=expired_subscription,
            plan_type="week",
            first_name="Test"
        )

        # Should be active and in the future
        assert result.status == SubscriptionStatus.ACTIVE
        assert result.expires_at > datetime.utcnow()

    # ============== CANCEL SUBSCRIPTION ==============

    @pytest.mark.asyncio
    async def test_cancel_subscription(self, service, test_session, test_subscription, mock_marzban):
        """Successfully cancel subscription"""
        result = await service.cancel_subscription(
            session=test_session,
            subscription=test_subscription
        )

        assert result is True
        assert test_subscription.status == SubscriptionStatus.CANCELLED
        mock_marzban.delete_user.assert_called_once()

    # ============== CHECK EXPIRED SUBSCRIPTIONS ==============

    @pytest.mark.asyncio
    async def test_check_expired_subscriptions(self, service, test_session, expired_subscription, mock_marzban):
        """Expired subscriptions should be deactivated"""
        await service.check_expired_subscriptions(test_session)
        
        # Refresh from DB
        await test_session.refresh(expired_subscription)
        
        assert expired_subscription.status == SubscriptionStatus.CANCELLED
