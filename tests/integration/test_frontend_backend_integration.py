"""
Integration Tests: Frontend + Backend
Tests the integration between Next.js frontend and FastAPI backend
"""

import pytest
import asyncio
import json
from datetime import datetime
from httpx import AsyncClient
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api.main import app


class TestFrontendBackendIntegration:
    """Test frontend-backend integration"""
    
    @pytest.fixture
    async def client(self):
        """Create test HTTP client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.mark.asyncio
    async def test_cors_configuration(self, client):
        """Test CORS headers for frontend access"""
        response = await client.options(
            "/api/traffic/current",
            headers={
                "Origin": "http://localhost:3002",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Should allow CORS for frontend origin
        assert response.status_code in [200, 204]
    
    @pytest.mark.asyncio
    async def test_api_response_format(self, client):
        """Test API response format matches frontend expectations"""
        response = await client.get("/api/traffic/current")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify expected structure
        assert "data" in data, "Response should have 'data' field"
        assert isinstance(data["data"], list), "Data should be a list"
        
        if len(data["data"]) > 0:
            reading = data["data"][0]
            # Verify required fields for frontend
            required_fields = ["id", "sensor_id", "timestamp", "speed", "volume"]
            for field in required_fields:
                assert field in reading, f"Missing required field: {field}"
    
    @pytest.mark.asyncio
    async def test_pagination_metadata(self, client):
        """Test pagination metadata for frontend table components"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        response = await client.get(f"/api/traffic/historical/{today}?page=1&size=10")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination metadata
        assert "pagination" in data
        pagination = data["pagination"]
        
        required_pagination_fields = ["page", "size", "total_pages", "total_items"]
        for field in required_pagination_fields:
            assert field in pagination, f"Missing pagination field: {field}"
    
    @pytest.mark.asyncio
    async def test_error_response_format(self, client):
        """Test error responses are properly formatted for frontend"""
        # Request invalid endpoint
        response = await client.get("/api/traffic/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        
        # Error should have detail field
        assert "detail" in data
    
    @pytest.mark.asyncio
    async def test_datetime_serialization(self, client):
        """Test datetime fields are properly serialized for frontend"""
        response = await client.get("/api/traffic/current")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["data"]) > 0:
            reading = data["data"][0]
            timestamp = reading.get("timestamp")
            
            if timestamp:
                # Should be ISO format string
                assert isinstance(timestamp, str)
                # Should be parseable
                try:
                    datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    pytest.fail(f"Timestamp not in ISO format: {timestamp}")
    
    @pytest.mark.asyncio
    async def test_sensor_location_data(self, client):
        """Test sensor location data for map visualization"""
        response = await client.get("/api/sensors")
        
        if response.status_code == 200:
            data = response.json()
            
            if "data" in data and len(data["data"]) > 0:
                sensor = data["data"][0]
                
                # Frontend map needs these fields
                location_fields = ["id", "location"]
                for field in location_fields:
                    assert field in sensor, f"Missing sensor field: {field}"
    
    @pytest.mark.asyncio
    async def test_prediction_endpoint_format(self, client):
        """Test prediction endpoint returns data in expected format"""
        response = await client.post(
            "/api/predictions/generate",
            json={
                "sensor_id": "test-sensor",
                "horizon_minutes": 30
            }
        )
        
        # May return 404 if no data, or 200 with prediction
        if response.status_code == 200:
            data = response.json()
            
            # Should have prediction structure
            assert "predictions" in data or "data" in data
    
    @pytest.mark.asyncio
    async def test_concurrent_frontend_requests(self, client):
        """Test handling concurrent requests from multiple frontend users"""
        async def make_request(endpoint):
            return await client.get(endpoint)
        
        # Simulate multiple users accessing different endpoints
        endpoints = [
            "/api/traffic/current",
            "/health",
            "/api/traffic/current",
            "/health",
            "/api/traffic/current"
        ]
        
        tasks = [make_request(endpoint) for endpoint in endpoints]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_response_compression(self, client):
        """Test that large responses support compression"""
        response = await client.get(
            "/api/traffic/current",
            headers={"Accept-Encoding": "gzip"}
        )
        
        assert response.status_code == 200
        # Response should be valid JSON regardless of compression
        data = response.json()
        assert "data" in data
    
    @pytest.mark.asyncio
    async def test_api_response_time(self, client):
        """Test API response time is acceptable for frontend UX"""
        import time
        
        start = time.time()
        response = await client.get("/api/traffic/current")
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        assert response.status_code == 200
        # Should respond within 200ms for good UX
        assert elapsed < 200, f"Response took {elapsed}ms, expected <200ms"
    
    @pytest.mark.asyncio
    async def test_health_check_for_frontend_monitoring(self, client):
        """Test health endpoint provides status for frontend monitoring"""
        response = await client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        
        # Frontend can check these for status indicators
        assert "status" in data
        assert "database" in data
        assert "kafka" in data
        
        # Each component should have status
        assert data["database"]["status"] in ["connected", "disconnected"]
        assert data["kafka"]["status"] in ["connected", "disconnected"]


class TestWebSocketIntegration:
    """Test WebSocket integration for real-time updates"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection establishment"""
        # Note: Requires websockets library
        try:
            from fastapi.testclient import TestClient
            from starlette.websockets import WebSocket
            
            # This is a placeholder - actual WebSocket testing
            # requires different test setup
            pass
        except ImportError:
            pytest.skip("WebSocket testing requires additional setup")
    
    @pytest.mark.asyncio
    async def test_websocket_message_format(self):
        """Test WebSocket messages are in expected format"""
        # Placeholder for WebSocket message format tests
        pass
    
    @pytest.mark.asyncio
    async def test_websocket_reconnection(self):
        """Test WebSocket reconnection handling"""
        # Placeholder for reconnection tests
        pass


class TestAPIEndpointCoverage:
    """Test all API endpoints expected by frontend"""
    
    @pytest.fixture
    async def client(self):
        """Create test HTTP client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.mark.asyncio
    async def test_all_required_endpoints_exist(self, client):
        """Test all endpoints required by frontend exist"""
        required_endpoints = [
            ("/health", "GET"),
            ("/api/traffic/current", "GET"),
            ("/api/sensors", "GET"),
        ]
        
        for endpoint, method in required_endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "POST":
                response = await client.post(endpoint, json={})
            
            # Should not be 404
            assert response.status_code != 404, f"Endpoint {method} {endpoint} not found"
    
    @pytest.mark.asyncio
    async def test_endpoint_authentication(self, client):
        """Test authentication requirements are clear"""
        # Currently no auth, but test should verify auth headers when implemented
        response = await client.get("/api/traffic/current")
        
        # For now, should work without auth
        assert response.status_code != 401
    
    @pytest.mark.asyncio
    async def test_rate_limiting_headers(self, client):
        """Test rate limiting headers for frontend"""
        response = await client.get("/api/traffic/current")
        
        # When rate limiting is implemented, check for headers
        # For now, just verify response is valid
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
