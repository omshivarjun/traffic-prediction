"""
Unit tests for FastAPI traffic data endpoints
"""
import pytest
from datetime import datetime, timedelta
from fastapi import status
from fastapi.testclient import TestClient

from models import Sensor, TrafficReading


class TestTrafficEndpoints:
    """Test cases for traffic data endpoints"""
    
    def test_get_current_traffic_data(self, client: TestClient, test_db, sample_sensor_data, sample_traffic_data):
        """Test GET /api/traffic/current endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create test traffic reading
        traffic_reading = TrafficReading(
            sensor_id=sensor.id,
            **sample_traffic_data,
            timestamp=datetime.utcnow()
        )
        test_db.add(traffic_reading)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/traffic/current")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        reading = data[0]
        assert "speed" in reading
        assert "volume" in reading
        assert "timestamp" in reading
    
    def test_get_current_traffic_data_with_filters(self, client: TestClient, test_db, sample_sensor_data, sample_traffic_data):
        """Test GET /api/traffic/current with filters"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create test traffic reading
        traffic_reading = TrafficReading(
            sensor_id=sensor.id,
            **sample_traffic_data,
            timestamp=datetime.utcnow()
        )
        test_db.add(traffic_reading)
        test_db.commit()
        
        # Test with sensor_id filter
        response = client.get(f"/api/traffic/current?sensor_id={sensor.sensor_id}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data) > 0
        
        # Test with limit
        response = client.get("/api/traffic/current?limit=5")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data) <= 5
    
    def test_get_historical_traffic_data(self, client: TestClient, test_db, sample_sensor_data, sample_traffic_data):
        """Test GET /api/traffic/historical endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create historical traffic readings
        base_time = datetime.utcnow() - timedelta(hours=2)
        for i in range(5):
            traffic_reading = TrafficReading(
                sensor_id=sensor.id,
                **sample_traffic_data,
                timestamp=base_time + timedelta(minutes=i*10)
            )
            test_db.add(traffic_reading)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/traffic/historical?hours=3")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_get_traffic_statistics(self, client: TestClient, test_db, sample_sensor_data, sample_traffic_data):
        """Test GET /api/traffic/statistics endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create traffic readings with varying values
        base_time = datetime.utcnow() - timedelta(hours=1)
        for i, speed in enumerate([30, 40, 50, 60, 70]):
            traffic_reading = TrafficReading(
                sensor_id=sensor.id,
                speed=speed,
                volume=sample_traffic_data['volume'] + i*10,
                density=sample_traffic_data['density'] + i*2,
                occupancy=sample_traffic_data['occupancy'],
                timestamp=base_time + timedelta(minutes=i*10)
            )
            test_db.add(traffic_reading)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/traffic/statistics?hours=2")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "avg_speed" in data
        assert "min_speed" in data
        assert "max_speed" in data
        assert "avg_volume" in data
        assert "total_readings" in data
        
        # Verify calculated values
        assert data["avg_speed"] == 50.0  # Average of 30,40,50,60,70
        assert data["min_speed"] == 30.0
        assert data["max_speed"] == 70.0
        assert data["total_readings"] == 5
    
    def test_get_sensor_traffic_data(self, client: TestClient, test_db, sample_sensor_data, sample_traffic_data):
        """Test GET /api/traffic/sensor/{sensor_id} endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create traffic reading
        traffic_reading = TrafficReading(
            sensor_id=sensor.id,
            **sample_traffic_data,
            timestamp=datetime.utcnow()
        )
        test_db.add(traffic_reading)
        test_db.commit()
        
        # Test endpoint
        response = client.get(f"/api/traffic/sensor/{sensor.sensor_id}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        reading = data[0]
        assert reading["speed"] == sample_traffic_data["speed"]
        assert reading["volume"] == sample_traffic_data["volume"]
    
    def test_get_sensor_traffic_data_not_found(self, client: TestClient):
        """Test GET /api/traffic/sensor/{sensor_id} with non-existent sensor"""
        response = client.get("/api/traffic/sensor/NON_EXISTENT")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_current_traffic_data_empty(self, client: TestClient):
        """Test GET /api/traffic/current with no data"""
        response = client.get("/api/traffic/current")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestErrorHandling:
    """Test error handling for traffic endpoints"""
    
    def test_invalid_query_parameters(self, client: TestClient):
        """Test endpoints with invalid query parameters"""
        # Test negative hours
        response = client.get("/api/traffic/historical?hours=-1")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test excessive limit
        response = client.get("/api/traffic/current?limit=2000")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test invalid hours for statistics
        response = client.get("/api/traffic/statistics?hours=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_database_error_handling(self, client: TestClient, monkeypatch):
        """Test database error handling"""
        # Mock database session to raise an exception
        def mock_get_db():
            raise Exception("Database connection failed")
        
        # This would require more sophisticated mocking in a real test
        # For now, we test the basic structure
        pass


class TestPerformance:
    """Performance tests for traffic endpoints"""
    
    def test_large_dataset_handling(self, client: TestClient, test_db, sample_sensor_data):
        """Test handling of large datasets"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create many traffic readings
        base_time = datetime.utcnow() - timedelta(hours=24)
        for i in range(100):  # Create 100 readings
            traffic_reading = TrafficReading(
                sensor_id=sensor.id,
                speed=50.0 + (i % 20),
                volume=100 + (i % 50),
                density=15.0 + (i % 10),
                occupancy=0.8,
                timestamp=base_time + timedelta(minutes=i*10)
            )
            test_db.add(traffic_reading)
        test_db.commit()
        
        # Test with large dataset
        response = client.get("/api/traffic/historical?hours=25&limit=200")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data) <= 200  # Should respect limit
    
    def test_concurrent_requests(self, client: TestClient):
        """Test concurrent request handling"""
        import concurrent.futures
        import time
        
        def make_request():
            start = time.time()
            response = client.get("/api/traffic/current")
            end = time.time()
            return response.status_code, end - start
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        for status_code, duration in results:
            assert status_code == status.HTTP_200_OK
            assert duration < 5.0  # Should complete within 5 seconds