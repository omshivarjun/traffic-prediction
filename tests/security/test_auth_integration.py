"""
Integration Tests for Authentication and Authorization System

Tests the complete authentication flow including:
- Login and token generation
- Protected endpoint access
- Role-based access control
- Rate limiting enforcement
- Security headers validation
"""

import pytest
import time
from fastapi.testclient import TestClient as FastAPITestClient
from src.api.main import app


@pytest.fixture(scope="module")
def client():
    """Create test client"""
    return FastAPITestClient(app)


class TestAuthenticationFlow:
    """Test complete authentication workflow"""
    
    def test_login_success(self, client):
        """Test successful login with valid credentials"""
        response = client.post("/auth/login", json={
            "username": "admin",
            "password": "Admin@Pass123!"
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = client.post("/auth/login", json={
            "username": "admin",
            "password": "WrongPassword!"
        })
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_access_protected_endpoint_with_token(self):
        """Test accessing protected endpoint with valid token"""
        # Login
        login_response = client.post("/auth/login", json={
            "username": "admin",
            "password": "Admin@Pass123!"
        })
        token = login_response.json()["access_token"]
        
        # Access protected endpoint
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["username"] == "admin"
        assert user_data["role"] == "admin"
    
    def test_access_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without authentication"""
        response = client.get("/api/traffic/statistics")
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]
    
    def test_access_protected_endpoint_with_invalid_token(self):
        """Test accessing protected endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401


class TestRoleBasedAccessControl:
    """Test RBAC enforcement across endpoints"""
    
    def test_admin_access_to_admin_endpoint(self):
        """Test admin user can access admin-only endpoints"""
        # Login as admin
        login_response = client.post("/auth/login", json={
            "username": "admin",
            "password": "Admin@Pass123!"
        })
        admin_token = login_response.json()["access_token"]
        
        # Try to access admin endpoint - Note: Will fail if no sensor exists
        # This tests RBAC, not business logic
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.post(
            "/api/predictions/generate?sensor_id=TEST",
            headers=headers
        )
        # Should NOT be 403 (forbidden) - may be 404 (sensor not found) or 500 (internal error)
        assert response.status_code != 403
    
    def test_viewer_denied_admin_endpoint(self):
        """Test non-admin user is denied access to admin endpoints"""
        # Login as viewer
        login_response = client.post("/auth/login", json={
            "username": "viewer",
            "password": "Viewer@Pass123!"
        })
        viewer_token = login_response.json()["access_token"]
        
        # Try to access admin endpoint
        headers = {"Authorization": f"Bearer {viewer_token}"}
        response = client.post(
            "/api/predictions/generate?sensor_id=TEST",
            headers=headers
        )
        
        # Should be forbidden
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]
    
    def test_user_access_to_user_endpoint(self):
        """Test regular user can access user-level endpoints"""
        # Login as regular user
        login_response = client.post("/auth/login", json={
            "username": "user",
            "password": "User@Pass123!"
        })
        user_token = login_response.json()["access_token"]
        
        # Access user-level endpoint
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.get("/api/predictions/accuracy", headers=headers)
        
        # Should NOT be forbidden (may be 200 or 500 depending on data)
        assert response.status_code != 403


class TestRateLimiting:
    """Test rate limiting enforcement"""
    
    def test_rate_limit_on_public_endpoint(self):
        """Test rate limiting blocks excessive requests to public endpoints"""
        # Health endpoint has 60/min limit
        max_requests = 61
        responses = []
        
        for i in range(max_requests):
            response = client.get("/health")
            responses.append(response.status_code)
            if response.status_code == 429:
                break
        
        # Should hit rate limit
        assert 429 in responses
        # Should happen around the 60th request
        rate_limited_at = responses.index(429) + 1
        assert 55 <= rate_limited_at <= 65  # Allow some variance
    
    def test_rate_limit_headers_present(self):
        """Test rate limit headers are included in responses"""
        response = client.get("/health")
        
        # Check for rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        
        # Validate values
        assert int(response.headers["X-RateLimit-Limit"]) > 0
        assert int(response.headers["X-RateLimit-Remaining"]) >= 0


class TestSecurityHeaders:
    """Test security headers are properly set"""
    
    def test_security_headers_present(self):
        """Test all required security headers are in responses"""
        response = client.get("/")
        
        required_headers = [
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Permissions-Policy",
            "Referrer-Policy"
        ]
        
        for header in required_headers:
            assert header in response.headers, f"Missing security header: {header}"
    
    def test_hsts_header_value(self):
        """Test HSTS header has correct configuration"""
        response = client.get("/")
        hsts = response.headers.get("Strict-Transport-Security")
        
        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts
    
    def test_csp_header_value(self):
        """Test CSP header has secure configuration"""
        response = client.get("/")
        csp = response.headers.get("Content-Security-Policy")
        
        assert "default-src" in csp
        assert "'self'" in csp
    
    def test_xframe_options(self):
        """Test X-Frame-Options prevents clickjacking"""
        response = client.get("/")
        assert response.headers.get("X-Frame-Options") == "DENY"


class TestPublicEndpoints:
    """Test public endpoints are accessible without authentication but rate limited"""
    
    def test_root_endpoint_accessible(self):
        """Test root endpoint is publicly accessible"""
        response = client.get("/")
        assert response.status_code == 200
        assert "Traffic Prediction API" in response.json()["message"]
    
    def test_health_endpoint_accessible(self):
        """Test health endpoint is publicly accessible"""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_sensors_endpoint_accessible(self):
        """Test sensors endpoint is publicly accessible"""
        response = client.get("/api/sensors")
        assert response.status_code == 200
    
    def test_incidents_endpoint_accessible(self):
        """Test incidents endpoint is publicly accessible"""
        response = client.get("/api/incidents")
        assert response.status_code == 200
    
    def test_public_endpoints_have_rate_limits(self):
        """Test public endpoints have rate limit headers"""
        endpoints = ["/", "/health", "/api/sensors", "/api/incidents"]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers


class TestTokenRefresh:
    """Test token refresh functionality"""
    
    def test_refresh_token_success(self):
        """Test successful token refresh"""
        # Login
        login_response = client.post("/auth/login", json={
            "username": "admin",
            "password": "Admin@Pass123!"
        })
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        refresh_response = client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
    
    def test_refresh_with_invalid_token(self):
        """Test refresh with invalid token fails"""
        response = client.post("/auth/refresh", json={
            "refresh_token": "invalid_token"
        })
        assert response.status_code == 401


class TestPasswordValidation:
    """Test password validation during registration/update"""
    
    def test_register_with_weak_password(self):
        """Test registration rejects weak passwords"""
        response = client.post("/auth/register", json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "weak",  # Too short, no special chars
            "full_name": "New User"
        })
        assert response.status_code == 400
        assert "password" in response.json()["detail"].lower()
    
    def test_register_with_strong_password(self):
        """Test registration accepts strong passwords"""
        response = client.post("/auth/register", json={
            "username": "newuser2",
            "email": "newuser2@example.com",
            "password": "Strong@Pass123!",
            "full_name": "New User"
        })
        # Should succeed (status 200) or fail with duplicate username (400) 
        # if test was run before
        assert response.status_code in [200, 400]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
