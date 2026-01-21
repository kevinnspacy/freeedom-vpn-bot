# Tests for MarzbanService
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from services.marzban_service import MarzbanService


class TestMarzbanService:
    """Test suite for MarzbanService"""

    @pytest.fixture
    def service(self):
        """Create MarzbanService instance with mocked settings"""
        with patch("services.marzban_service.settings") as mock_settings:
            mock_settings.MARZBAN_API_URL = "https://test-marzban.example.com"
            mock_settings.MARZBAN_USERNAME = "test_admin"
            mock_settings.MARZBAN_PASSWORD = "test_password"
            return MarzbanService()

    # ============== USERNAME GENERATION ==============

    def test_generate_username_basic(self):
        """Generate username with basic Latin name"""
        result = MarzbanService.generate_username(123456, "John", "month")
        
        assert result.startswith("FreedomVPN_")
        assert "john" in result.lower()
        assert len(result) <= 50

    def test_generate_username_cyrillic(self):
        """Generate username with Cyrillic name (transliteration)"""
        result = MarzbanService.generate_username(123456, "Иван", "trial")
        
        assert result.startswith("FreedomVPN_")
        assert "ivan" in result.lower()

    def test_generate_username_special_chars(self):
        """Special characters should be removed"""
        result = MarzbanService.generate_username(123456, "Test@User#123!", "day")
        
        assert result.startswith("FreedomVPN_")
        assert "@" not in result
        assert "#" not in result
        assert "!" not in result

    def test_generate_username_empty_name(self):
        """Empty name should default to 'user'"""
        result = MarzbanService.generate_username(123456, "", "week")
        
        assert result.startswith("FreedomVPN_")
        assert "user" in result.lower()

    def test_generate_username_unique(self):
        """Each call should generate unique username (random suffix)"""
        result1 = MarzbanService.generate_username(123456, "Test", "month")
        result2 = MarzbanService.generate_username(123456, "Test", "month")
        
        assert result1 != result2

    # ============== EXPIRE TIMESTAMP CALCULATION ==============

    def test_calculate_expire_trial(self, service):
        """Trial should expire in 72 hours"""
        result = service.calculate_expire_timestamp("trial")
        expected = int((datetime.now() + timedelta(hours=72)).timestamp())
        
        # Allow 5 second tolerance
        assert abs(result - expected) < 5

    def test_calculate_expire_day(self, service):
        """Day plan should expire in 1 day"""
        result = service.calculate_expire_timestamp("day")
        expected = int((datetime.now() + timedelta(days=1)).timestamp())
        
        assert abs(result - expected) < 5

    def test_calculate_expire_week(self, service):
        """Week plan should expire in 7 days"""
        result = service.calculate_expire_timestamp("week")
        expected = int((datetime.now() + timedelta(weeks=1)).timestamp())
        
        assert abs(result - expected) < 5

    def test_calculate_expire_month(self, service):
        """Month plan should expire in 30 days"""
        result = service.calculate_expire_timestamp("month")
        expected = int((datetime.now() + timedelta(days=30)).timestamp())
        
        assert abs(result - expected) < 5

    def test_calculate_expire_3month(self, service):
        """3-month plan should expire in 90 days"""
        result = service.calculate_expire_timestamp("3month")
        expected = int((datetime.now() + timedelta(days=90)).timestamp())
        
        assert abs(result - expected) < 5

    def test_calculate_expire_year(self, service):
        """Year plan should expire in 365 days"""
        result = service.calculate_expire_timestamp("year")
        expected = int((datetime.now() + timedelta(days=365)).timestamp())
        
        assert abs(result - expected) < 5

    def test_calculate_expire_invalid(self, service):
        """Invalid plan type should raise ValueError"""
        with pytest.raises(ValueError, match="Unknown plan type"):
            service.calculate_expire_timestamp("invalid")

    # ============== NOTE GENERATION ==============

    def test_generate_note_trial(self, service):
        """Generate note for trial subscription"""
        expire_ts = int((datetime.now() + timedelta(hours=72)).timestamp())
        result = service._generate_note("trial", "Тест", expire_ts)
        
        assert "FreedomVPN" in result
        assert "🎁" in result  # Trial emoji
        assert "freeddomm_bot" in result

    def test_generate_note_paid(self, service):
        """Generate note for paid subscription"""
        expire_ts = int((datetime.now() + timedelta(days=30)).timestamp())
        result = service._generate_note("month", "User", expire_ts)
        
        assert "💎" in result  # Paid emoji
        assert "FreedomVPN" in result

    # ============== API CALLS (MOCKED) ==============

    @pytest.mark.asyncio
    async def test_get_token(self, service):
        """Token should be fetched and cached"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_token_123"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            token = await service._get_token()
            
            assert token == "test_token_123"
            assert service._token == "test_token_123"
            assert service._token_expires is not None

    @pytest.mark.asyncio
    async def test_create_user_success(self, service):
        """Successfully create user in Marzban"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "username": "FreedomVPN_test_abc1",
            "subscription_url": "https://test.com/sub/123",
            "status": "active"
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.text = '{"username": "test"}'

        with patch.object(service, "_get_token", return_value="fake_token"):
            with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                result = await service.create_user(
                    telegram_id=123456,
                    plan_type="trial",
                    first_name="Test"
                )
                
                assert result["username"] == "FreedomVPN_test_abc1"
                assert result["subscription_url"] is not None

    @pytest.mark.asyncio
    async def test_get_all_users(self, service):
        """Get all users from Marzban"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "users": [
                {"username": "user1", "status": "active"},
                {"username": "user2", "status": "active"}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.text = '{"users": []}'

        with patch.object(service, "_get_token", return_value="fake_token"):
            with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                result = await service.get_all_users()
                
                assert len(result) == 2
                assert result[0]["username"] == "user1"

    # ============== QR CODE ==============

    def test_generate_qr_code_url(self, service):
        """Generate valid QR code URL"""
        result = service.generate_qr_code_url("vless://example")
        
        assert "api.qrserver.com" in result
        assert "vless" in result
