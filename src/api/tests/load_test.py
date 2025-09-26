"""
Load testing configuration using Locust for FastAPI backend
"""
from locust import HttpUser, task, between
import json
import random
from datetime import datetime, timedelta


class TrafficAPIUser(HttpUser):
    """Simulated user for traffic API load testing"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    def on_start(self):
        """Setup user session"""
        self.sensor_ids = [
            "SENSOR_001", "SENSOR_002", "SENSOR_003", 
            "SENSOR_004", "SENSOR_005"
        ]
    
    @task(3)
    def get_current_traffic(self):
        """Test current traffic data endpoint (high frequency)"""
        params = {
            "limit": random.randint(10, 50)
        }
        
        # Sometimes filter by sensor
        if random.random() < 0.3:
            params["sensor_id"] = random.choice(self.sensor_ids)
        
        with self.client.get("/api/traffic/current", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    response.success()
                else:
                    response.failure("Expected list response")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(2)
    def get_historical_traffic(self):
        """Test historical traffic data endpoint"""
        params = {
            "hours": random.randint(1, 24),
            "limit": random.randint(50, 200)
        }
        
        # Sometimes filter by sensor
        if random.random() < 0.4:
            params["sensor_id"] = random.choice(self.sensor_ids)
        
        with self.client.get("/api/traffic/historical", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    response.success()
                else:
                    response.failure("Expected list response")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_traffic_statistics(self):
        """Test traffic statistics endpoint"""
        params = {
            "hours": random.randint(1, 48)
        }
        
        # Sometimes filter by sensor
        if random.random() < 0.3:
            params["sensor_id"] = random.choice(self.sensor_ids)
        
        with self.client.get("/api/traffic/statistics", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                expected_fields = ["avg_speed", "min_speed", "max_speed", "total_readings"]
                if all(field in data for field in expected_fields):
                    response.success()
                else:
                    response.failure("Missing expected fields in statistics")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_sensor_traffic(self):
        """Test sensor-specific traffic data endpoint"""
        sensor_id = random.choice(self.sensor_ids)
        params = {
            "hours": random.randint(1, 12),
            "limit": random.randint(20, 100)
        }
        
        with self.client.get(f"/api/traffic/sensor/{sensor_id}", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    response.success()
                else:
                    response.failure("Expected list response")
            elif response.status_code == 404:
                # Sensor not found is acceptable for test data
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(2)
    def get_latest_predictions(self):
        """Test latest predictions endpoint"""
        params = {
            "limit": random.randint(10, 50)
        }
        
        # Sometimes add filters
        if random.random() < 0.3:
            params["sensor_id"] = random.choice(self.sensor_ids)
        
        if random.random() < 0.3:
            params["min_confidence"] = random.uniform(0.7, 0.9)
        
        with self.client.get("/api/predictions/latest", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    response.success()
                else:
                    response.failure("Expected list response")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_prediction_accuracy(self):
        """Test prediction accuracy endpoint"""
        params = {
            "hours": random.randint(12, 72)
        }
        
        # Sometimes filter by sensor
        if random.random() < 0.3:
            params["sensor_id"] = random.choice(self.sensor_ids)
        
        with self.client.get("/api/predictions/accuracy", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                expected_fields = ["avg_confidence", "total_predictions"]
                if all(field in data for field in expected_fields):
                    response.success()
                else:
                    response.failure("Missing expected fields in accuracy data")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_congestion_analytics(self):
        """Test congestion analytics endpoint"""
        params = {
            "hours": random.randint(6, 48)
        }
        
        # Sometimes filter by sensor
        if random.random() < 0.3:
            params["sensor_id"] = random.choice(self.sensor_ids)
        
        with self.client.get("/api/analytics/congestion", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "metric_name" in data and data["metric_name"] == "traffic_congestion":
                    response.success()
                else:
                    response.failure("Invalid congestion analytics response")
            elif response.status_code == 404:
                # Sensor not found is acceptable
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_pattern_analytics(self):
        """Test pattern analytics endpoint"""
        params = {
            "days": random.randint(3, 14)
        }
        
        # Sometimes filter by sensor
        if random.random() < 0.3:
            params["sensor_id"] = random.choice(self.sensor_ids)
        
        with self.client.get("/api/analytics/patterns", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "metric_name" in data and data["metric_name"] == "traffic_patterns":
                    response.success()
                else:
                    response.failure("Invalid pattern analytics response")
            elif response.status_code == 404:
                # Sensor not found is acceptable
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_trend_analytics(self):
        """Test trend analytics endpoint"""
        params = {
            "days": random.randint(7, 30)
        }
        
        # Sometimes filter by sensor
        if random.random() < 0.3:
            params["sensor_id"] = random.choice(self.sensor_ids)
        
        with self.client.get("/api/analytics/trends", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "metric_name" in data and data["metric_name"] == "traffic_trends":
                    response.success()
                else:
                    response.failure("Invalid trend analytics response")
            elif response.status_code == 404:
                # Sensor not found is acceptable
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_sensors(self):
        """Test sensors list endpoint"""
        params = {
            "limit": random.randint(50, 200)
        }
        
        # Sometimes filter by status
        if random.random() < 0.3:
            params["status"] = random.choice(["active", "inactive", "maintenance"])
        
        with self.client.get("/api/sensors", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    response.success()
                else:
                    response.failure("Expected list response")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_incidents(self):
        """Test incidents endpoint"""
        params = {
            "hours": random.randint(6, 72)
        }
        
        # Sometimes filter by status
        if random.random() < 0.5:
            params["status"] = random.choice(["active", "resolved", "investigating"])
        
        with self.client.get("/api/incidents", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    response.success()
                else:
                    response.failure("Expected list response")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_health_check(self):
        """Test health check endpoint"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "healthy":
                    response.success()
                else:
                    response.failure("Health check failed")
            else:
                response.failure(f"Status code: {response.status_code}")


class PredictionGenerationUser(HttpUser):
    """Specialized user for testing prediction generation (lower frequency)"""
    
    wait_time = between(5, 15)  # Longer wait times for expensive operations
    
    def on_start(self):
        """Setup user session"""
        self.sensor_ids = [
            "SENSOR_001", "SENSOR_002", "SENSOR_003"
        ]
    
    @task(1)
    def generate_prediction(self):
        """Test prediction generation endpoint"""
        sensor_id = random.choice(self.sensor_ids)
        request_data = {
            "sensor_id": sensor_id,
            "horizon_minutes": random.choice([15, 30, 60])
        }
        
        with self.client.post("/api/predictions/generate", 
                             json=request_data, 
                             catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "message" in data and "prediction_id" in data:
                    response.success()
                else:
                    response.failure("Invalid prediction generation response")
            elif response.status_code == 404:
                # Sensor not found is acceptable for test data
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")


class WebSocketUser(HttpUser):
    """User for testing WebSocket connections (if needed)"""
    
    wait_time = between(10, 30)
    
    # Note: Locust doesn't natively support WebSocket testing
    # This would require additional libraries like websocket-client
    # For now, we'll focus on HTTP endpoint testing
    
    @task(1)
    def test_websocket_connection(self):
        """Placeholder for WebSocket testing"""
        # This would require additional implementation
        # using websocket-client or similar library
        pass