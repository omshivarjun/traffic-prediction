"""
Integration Tests: Database + API Layer
Tests the integration between PostgreSQL database and FastAPI endpoints
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from httpx import AsyncClient
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api.main import app
from src.api.database import db_manager


class TestDatabaseAPIIntegration:
    """Test database and API integration"""
    
    @pytest.fixture
    async def client(self):
        """Create test client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health endpoint returns database status"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert "database" in data
            assert data["database"]["status"] == "connected"
    
    @pytest.mark.asyncio
    async def test_current_traffic_data_retrieval(self):
        """Test retrieving current traffic data from database via API"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/traffic/current")
            assert response.status_code == 200
            
            data = response.json()
            assert "data" in data
            # May be empty, that's OK
    
    @pytest.mark.asyncio
    async def test_historical_traffic_data_retrieval(self):
        """Test retrieving historical traffic data with pagination"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            response = await client.get(f"/api/traffic/historical/{today}?page=1&size=5")
            assert response.status_code == 200
            
            data = response.json()
            assert "data" in data
            assert "pagination" in data
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["size"] == 5
        """Setup test data in database"""
        test_data = []
        
        async with db_manager.async_session_scope() as session:
            # Get or create test sensor
            result = await session.execute(
                text("SELECT id FROM traffic.sensors LIMIT 1")
            )
            sensor_id = result.scalar()
            
            if not sensor_id:
                # Create test sensor if none exists
                result = await session.execute(
                    text("""
                        INSERT INTO traffic.sensors (location, sensor_type, status)
                        VALUES ('Test Location', 'test_sensor', 'active')
                        RETURNING id
                    """)
                )
                sensor_id = result.scalar()
                await session.commit()
            
            # Insert test traffic readings
            base_time = datetime.utcnow() - timedelta(hours=1)
            for i in range(10):
                timestamp = base_time + timedelta(minutes=i * 5)
                await session.execute(
                    text("""
                        INSERT INTO traffic.traffic_readings 
                        (sensor_id, timestamp, speed, volume, occupancy)
                        VALUES (:sensor_id, :timestamp, :speed, :volume, :occupancy)
                    """),
                    {
                        'sensor_id': sensor_id,
                        'timestamp': timestamp,
                        'speed': 55.0 + i,
                        'volume': 1000 + i * 50,
                        'occupancy': 0.6 + i * 0.02
                    }
                )
                test_data.append({
                    'sensor_id': sensor_id,
                    'timestamp': timestamp,
                    'speed': 55.0 + i,
                    'volume': 1000 + i * 50
                })
            
            await session.commit()
        
        yield test_data
        
        # Cleanup
        async with db_manager.async_session_scope() as session:
            await session.execute(
                text("DELETE FROM traffic.traffic_readings WHERE sensor_id = :sensor_id"),
                {'sensor_id': sensor_id}
            )
            await session.commit()
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test health endpoint returns database status"""
        response = await client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert data["database"]["status"] == "connected"
    
    @pytest.mark.asyncio
    async def test_current_traffic_data_retrieval(self, client, setup_test_data):
        """Test retrieving current traffic data from database via API"""
        response = await client.get("/api/traffic/current")
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0
        
        # Verify data structure
        reading = data["data"][0]
        assert "sensor_id" in reading
        assert "timestamp" in reading
        assert "speed" in reading
        assert "volume" in reading
    
    @pytest.mark.asyncio
    async def test_historical_traffic_data_retrieval(self, client, setup_test_data):
        """Test retrieving historical traffic data with pagination"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        response = await client.get(f"/api/traffic/historical/{today}?page=1&size=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["size"] == 5
    
    @pytest.mark.asyncio
    async def test_traffic_data_filtering(self, client, setup_test_data):
        """Test filtering traffic data by sensor"""
        test_data = await setup_test_data.__anext__()
        sensor_id = str(test_data[0]['sensor_id'])
        
        response = await client.get(f"/api/traffic/sensor/{sensor_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["data"]) > 0
        
        # Verify all readings are from the correct sensor
        for reading in data["data"]:
            assert reading["sensor_id"] == sensor_id
    
    @pytest.mark.asyncio
    async def test_database_transaction_integrity(self):
        """Test database transaction rollback on error"""
        async with db_manager.async_session_scope() as session:
            # Get sensor
            result = await session.execute(
                text("SELECT id FROM traffic.sensors LIMIT 1")
            )
            sensor_id = result.scalar()
            
            try:
                # Insert valid data
                await session.execute(
                    text("""
                        INSERT INTO traffic.traffic_readings 
                        (sensor_id, timestamp, speed, volume, occupancy)
                        VALUES (:sensor_id, :timestamp, :speed, :volume, :occupancy)
                    """),
                    {
                        'sensor_id': sensor_id,
                        'timestamp': datetime.utcnow(),
                        'speed': 60.0,
                        'volume': 1200,
                        'occupancy': 0.7
                    }
                )
                
                # Force error with invalid data
                await session.execute(
                    text("""
                        INSERT INTO traffic.traffic_readings 
                        (sensor_id, timestamp, speed, volume, occupancy)
                        VALUES (:sensor_id, :timestamp, :speed, :volume, :occupancy)
                    """),
                    {
                        'sensor_id': sensor_id,
                        'timestamp': datetime.utcnow(),
                        'speed': 'invalid',  # This should fail
                        'volume': 1200,
                        'occupancy': 0.7
                    }
                )
                
                await session.commit()
                assert False, "Should have raised error"
                
            except Exception:
                # Transaction should rollback
                await session.rollback()
        
        # Verify no data was inserted
        async with db_manager.async_session_scope() as session:
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM traffic.traffic_readings 
                    WHERE sensor_id = :sensor_id AND speed = 60.0
                """),
                {'sensor_id': sensor_id}
            )
            count = result.scalar()
            assert count == 0, "Transaction should have been rolled back"
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, client, setup_test_data):
        """Test handling concurrent API requests"""
        async def make_request():
            return await client.get("/api/traffic/current")
        
        # Make 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
    
    @pytest.mark.asyncio
    async def test_data_consistency_across_endpoints(self, client, setup_test_data):
        """Test data consistency between different API endpoints"""
        # Get current data
        current_response = await client.get("/api/traffic/current")
        current_data = current_response.json()["data"]
        
        if len(current_data) > 0:
            # Get historical data for same period
            timestamp = current_data[0]["timestamp"]
            date = timestamp.split("T")[0]
            
            historical_response = await client.get(f"/api/traffic/historical/{date}")
            historical_data = historical_response.json()["data"]
            
            # Find matching record
            matching = [r for r in historical_data if r["id"] == current_data[0]["id"]]
            assert len(matching) > 0, "Same data should be in both endpoints"
            assert matching[0]["speed"] == current_data[0]["speed"]


class TestDatabasePerformance:
    """Test database query performance"""
    
    @pytest.mark.asyncio
    async def test_query_performance_current_data(self):
        """Test current data query executes in <100ms"""
        import time
        
        async with db_manager.async_session_scope() as session:
            start = time.time()
            
            result = await session.execute(
                text("""
                    SELECT * FROM traffic.traffic_readings 
                    WHERE timestamp >= NOW() - INTERVAL '5 minutes'
                    ORDER BY timestamp DESC
                    LIMIT 100
                """)
            )
            rows = result.fetchall()
            
            elapsed = (time.time() - start) * 1000  # Convert to ms
            
            assert elapsed < 100, f"Query took {elapsed}ms, expected <100ms"
    
    @pytest.mark.asyncio
    async def test_query_performance_historical_data(self):
        """Test historical data query with index usage"""
        import time
        
        async with db_manager.async_session_scope() as session:
            start = time.time()
            
            result = await session.execute(
                text("""
                    SELECT * FROM traffic.traffic_readings 
                    WHERE timestamp >= NOW() - INTERVAL '1 day'
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """)
            )
            rows = result.fetchall()
            
            elapsed = (time.time() - start) * 1000
            
            # Historical queries can be slightly slower but should still be fast
            assert elapsed < 500, f"Query took {elapsed}ms, expected <500ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
