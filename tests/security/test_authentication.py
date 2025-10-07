"""
Security Testing Suite
Tests for authentication, authorization, and security features
"""

import pytest
from fastapi.testclient import TestClient
from datetime import timedelta

from src.api.security import (
    SecurityUtils, UserCreate, UserLogin, PasswordChange,
    UserRepository, USERS_DB
)
from src.api.auth import router as auth_router

# Test data
TEST_USER_DATA = {
    "username": "testuser",
    "email": "test@example.com",
    "password": "Test@Password123",
    "full_name": "Test User",
    "role": "user"
}

ADMIN_CREDENTIALS = {
    "username": "admin",
    "password": "Admin@123456789"
}

USER_CREDENTIALS = {
    "username": "user",
    "password": "User@123456789"
}


class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_password_hashing(self):
        """Test password can be hashed"""
        password = "Test@Password123"
        hashed = SecurityUtils.get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 50  # bcrypt hashes are long
    
    def test_password_verification_success(self):
        """Test correct password verification"""
        password = "Test@Password123"
        hashed = SecurityUtils.get_password_hash(password)
        
        assert SecurityUtils.verify_password(password, hashed)
    
    def test_password_verification_failure(self):
        """Test incorrect password is rejected"""
        password = "Test@Password123"
        wrong_password = "Wrong@Password456"
        hashed = SecurityUtils.get_password_hash(password)
        
        assert not SecurityUtils.verify_password(wrong_password, hashed)
    
    def test_password_hash_unique(self):
        """Test same password generates different hashes (salt)"""
        password = "Test@Password123"
        hash1 = SecurityUtils.get_password_hash(password)
        hash2 = SecurityUtils.get_password_hash(password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        # But both should verify correctly
        assert SecurityUtils.verify_password(password, hash1)
        assert SecurityUtils.verify_password(password, hash2)


class TestPasswordValidation:
    """Test password complexity validation"""
    
    def test_password_minimum_length(self):
        """Test password must be at least 12 characters"""
        with pytest.raises(ValueError, match="at least 12 characters"):
            user = UserCreate(
                username="test",
                email="test@example.com",
                password="Short@1"  # Too short
            )
    
    def test_password_requires_uppercase(self):
        """Test password must contain uppercase letter"""
        with pytest.raises(ValueError, match="uppercase letter"):
            user = UserCreate(
                username="test",
                email="test@example.com",
                password="nouppercase@123"
            )
    
    def test_password_requires_lowercase(self):
        """Test password must contain lowercase letter"""
        with pytest.raises(ValueError, match="lowercase letter"):
            user = UserCreate(
                username="test",
                email="test@example.com",
                password="NOLOWERCASE@123"
            )
    
    def test_password_requires_digit(self):
        """Test password must contain digit"""
        with pytest.raises(ValueError, match="digit"):
            user = UserCreate(
                username="test",
                email="test@example.com",
                password="NoDigits@Here"
            )
    
    def test_password_requires_special_char(self):
        """Test password must contain special character"""
        with pytest.raises(ValueError, match="special character"):
            user = UserCreate(
                username="test",
                email="test@example.com",
                password="NoSpecial123Char"
            )
    
    def test_password_valid_complex(self):
        """Test valid complex password is accepted"""
        user = UserCreate(
            username="test",
            email="test@example.com",
            password="ValidPassword@123"
        )
        assert user.password == "ValidPassword@123"


class TestJWTTokens:
    """Test JWT token creation and validation"""
    
    def test_create_access_token(self):
        """Test access token creation"""
        data = {"sub": "testuser", "user_id": "123", "role": "user"}
        token = SecurityUtils.create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are long
    
    def test_create_refresh_token(self):
        """Test refresh token creation"""
        data = {"sub": "testuser", "user_id": "123"}
        token = SecurityUtils.create_refresh_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 100
    
    def test_decode_valid_token(self):
        """Test decoding valid token"""
        data = {"sub": "testuser", "user_id": "123", "role": "user"}
        token = SecurityUtils.create_access_token(data)
        
        decoded = SecurityUtils.decode_token(token)
        
        assert decoded["sub"] == "testuser"
        assert decoded["user_id"] == "123"
        assert decoded["role"] == "user"
        assert "exp" in decoded
        assert "iat" in decoded
    
    def test_decode_expired_token(self):
        """Test expired token is rejected"""
        from jose import JWTError
        
        data = {"sub": "testuser"}
        # Create token that expires immediately
        token = SecurityUtils.create_access_token(
            data,
            expires_delta=timedelta(seconds=-1)
        )
        
        with pytest.raises(JWTError):
            SecurityUtils.decode_token(token)
    
    def test_decode_invalid_token(self):
        """Test invalid token is rejected"""
        from jose import JWTError
        
        invalid_token = "invalid.token.string"
        
        with pytest.raises(JWTError):
            SecurityUtils.decode_token(invalid_token)
    
    def test_token_type_in_payload(self):
        """Test token type is included in payload"""
        data = {"sub": "testuser"}
        
        access_token = SecurityUtils.create_access_token(data)
        refresh_token = SecurityUtils.create_refresh_token(data)
        
        access_payload = SecurityUtils.decode_token(access_token)
        refresh_payload = SecurityUtils.decode_token(refresh_token)
        
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"


class TestRolePermissions:
    """Test role-based access control"""
    
    def test_viewer_has_viewer_permissions(self):
        """Test viewer role can access viewer resources"""
        assert SecurityUtils.check_role_permission("viewer", "viewer")
    
    def test_user_has_viewer_permissions(self):
        """Test user role can access viewer resources"""
        assert SecurityUtils.check_role_permission("user", "viewer")
    
    def test_user_has_user_permissions(self):
        """Test user role can access user resources"""
        assert SecurityUtils.check_role_permission("user", "user")
    
    def test_admin_has_all_permissions(self):
        """Test admin role can access all resources"""
        assert SecurityUtils.check_role_permission("admin", "viewer")
        assert SecurityUtils.check_role_permission("admin", "user")
        assert SecurityUtils.check_role_permission("admin", "admin")
    
    def test_viewer_cannot_access_user_resources(self):
        """Test viewer role cannot access user resources"""
        assert not SecurityUtils.check_role_permission("viewer", "user")
    
    def test_viewer_cannot_access_admin_resources(self):
        """Test viewer role cannot access admin resources"""
        assert not SecurityUtils.check_role_permission("viewer", "admin")
    
    def test_user_cannot_access_admin_resources(self):
        """Test user role cannot access admin resources"""
        assert not SecurityUtils.check_role_permission("user", "admin")


class TestUserRepository:
    """Test user repository operations"""
    
    def test_get_user_by_username(self):
        """Test retrieving user by username"""
        user = UserRepository.get_user_by_username("admin")
        
        assert user is not None
        assert user.username == "admin"
        assert user.role == "admin"
    
    def test_get_nonexistent_user(self):
        """Test retrieving nonexistent user returns None"""
        user = UserRepository.get_user_by_username("nonexistent")
        
        assert user is None
    
    def test_get_user_by_id(self):
        """Test retrieving user by ID"""
        user = UserRepository.get_user_by_id("1")
        
        assert user is not None
        assert user.id == "1"
        assert user.username == "admin"
    
    def test_create_user(self):
        """Test creating new user"""
        user_data = UserCreate(**TEST_USER_DATA)
        created_user = UserRepository.create_user(user_data)
        
        assert created_user.username == TEST_USER_DATA["username"]
        assert created_user.email == TEST_USER_DATA["email"]
        assert created_user.role == TEST_USER_DATA["role"]
        assert created_user.hashed_password != TEST_USER_DATA["password"]
        
        # Cleanup
        if TEST_USER_DATA["username"] in USERS_DB:
            del USERS_DB[TEST_USER_DATA["username"]]
    
    def test_list_users(self):
        """Test listing all users"""
        users = UserRepository.list_users()
        
        assert len(users) >= 3  # At least admin, user, viewer
        assert all(hasattr(user, "username") for user in users)
        assert all(not hasattr(user, "hashed_password") for user in users)


class TestAPIKeyGeneration:
    """Test API key generation"""
    
    def test_generate_api_key(self):
        """Test API key generation"""
        key = SecurityUtils.generate_api_key()
        
        assert key is not None
        assert isinstance(key, str)
        assert len(key) > 30  # URL-safe tokens are long
    
    def test_api_keys_unique(self):
        """Test generated API keys are unique"""
        key1 = SecurityUtils.generate_api_key()
        key2 = SecurityUtils.generate_api_key()
        
        assert key1 != key2


@pytest.mark.asyncio
class TestAuthenticationEndpoints:
    """Test authentication API endpoints (requires FastAPI app)"""
    
    # These tests would require the full FastAPI app to be set up
    # They are placeholders for when the app is integrated
    
    async def test_login_endpoint_placeholder(self):
        """Placeholder for login endpoint test"""
        pass
    
    async def test_refresh_token_endpoint_placeholder(self):
        """Placeholder for refresh token endpoint test"""
        pass
    
    async def test_protected_endpoint_placeholder(self):
        """Placeholder for protected endpoint test"""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
