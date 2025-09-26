"""
Unit tests for FastAPI prediction endpoints
"""
import pytest
from datetime import datetime, timedelta
from fastapi import status
from fastapi.testclient import TestClient

from models import Sensor, Prediction, ModelMetric


class TestPredictionEndpoints:
    """Test cases for prediction endpoints"""
    
    def test_get_latest_predictions(self, client: TestClient, test_db, sample_sensor_data, sample_prediction_data):
        """Test GET /api/predictions/latest endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create test prediction
        prediction = Prediction(
            sensor_id=sensor.id,
            **sample_prediction_data,
            prediction_timestamp=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        test_db.add(prediction)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/predictions/latest")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        pred = data[0]
        assert "predicted_speed" in pred
        assert "predicted_volume" in pred
        assert "confidence_score" in pred
        assert "prediction_horizon_minutes" in pred
    
    def test_get_latest_predictions_with_filters(self, client: TestClient, test_db, sample_sensor_data, sample_prediction_data):
        """Test GET /api/predictions/latest with filters"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create test prediction
        prediction = Prediction(
            sensor_id=sensor.id,
            **sample_prediction_data,
            prediction_timestamp=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        test_db.add(prediction)
        test_db.commit()
        
        # Test with sensor_id filter
        response = client.get(f"/api/predictions/latest?sensor_id={sensor.sensor_id}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data) > 0
        
        # Test with confidence threshold
        response = client.get("/api/predictions/latest?min_confidence=0.8")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        for pred in data:
            assert pred["confidence_score"] >= 0.8
    
    def test_get_prediction_accuracy(self, client: TestClient, test_db, sample_sensor_data, sample_prediction_data):
        """Test GET /api/predictions/accuracy endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create predictions with different accuracy scores
        base_time = datetime.utcnow() - timedelta(hours=1)
        for i, confidence in enumerate([0.8, 0.85, 0.9, 0.95]):
            prediction = Prediction(
                sensor_id=sensor.id,
                predicted_speed=sample_prediction_data["predicted_speed"],
                predicted_volume=sample_prediction_data["predicted_volume"],
                predicted_density=sample_prediction_data["predicted_density"],
                confidence_score=confidence,
                prediction_horizon_minutes=30,
                model_version="v1.0.0",
                prediction_timestamp=base_time + timedelta(minutes=i*10),
                created_at=base_time + timedelta(minutes=i*10)
            )
            test_db.add(prediction)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/predictions/accuracy?hours=2")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "avg_confidence" in data
        assert "total_predictions" in data
        assert "high_confidence_count" in data
        assert "accuracy_by_horizon" in data
        
        # Verify calculated values
        assert data["avg_confidence"] == 0.875  # Average of 0.8, 0.85, 0.9, 0.95
        assert data["total_predictions"] == 4
    
    def test_generate_prediction(self, client: TestClient, test_db, sample_sensor_data):
        """Test POST /api/predictions/generate endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Test prediction generation
        request_data = {
            "sensor_id": sensor.sensor_id,
            "horizon_minutes": 30
        }
        
        response = client.post("/api/predictions/generate", json=request_data)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "message" in data
        assert "prediction_id" in data
        assert "estimated_completion" in data
    
    def test_generate_prediction_invalid_sensor(self, client: TestClient):
        """Test POST /api/predictions/generate with invalid sensor"""
        request_data = {
            "sensor_id": "NON_EXISTENT",
            "horizon_minutes": 30
        }
        
        response = client.post("/api/predictions/generate", json=request_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_sensor_predictions(self, client: TestClient, test_db, sample_sensor_data, sample_prediction_data):
        """Test GET /api/predictions/sensor/{sensor_id} endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create test prediction
        prediction = Prediction(
            sensor_id=sensor.id,
            **sample_prediction_data,
            prediction_timestamp=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        test_db.add(prediction)
        test_db.commit()
        
        # Test endpoint
        response = client.get(f"/api/predictions/sensor/{sensor.sensor_id}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        pred = data[0]
        assert pred["predicted_speed"] == sample_prediction_data["predicted_speed"]


class TestAnalyticsEndpoints:
    """Test cases for analytics endpoints"""
    
    def test_get_congestion_analytics(self, client: TestClient, test_db, sample_sensor_data):
        """Test GET /api/analytics/congestion endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create traffic readings with different speeds for congestion analysis
        from models import TrafficReading
        base_time = datetime.utcnow() - timedelta(hours=5)
        
        # Create readings with varying congestion levels
        speeds = [25, 35, 55, 65, 20]  # Mix of high, medium, low congestion
        for i, speed in enumerate(speeds):
            reading = TrafficReading(
                sensor_id=sensor.id,
                speed=speed,
                volume=100 + i*10,
                density=15 + i*2,
                occupancy=0.8,
                timestamp=base_time + timedelta(hours=i)
            )
            test_db.add(reading)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/analytics/congestion?hours=6")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "metric_name" in data
        assert "time_period" in data
        assert "data_points" in data
        assert "summary" in data
        
        assert data["metric_name"] == "traffic_congestion"
        assert len(data["data_points"]) > 0
        
        # Check summary contains expected fields
        summary = data["summary"]
        assert "congestion_percentage" in summary
        assert "avg_speed_overall" in summary
    
    def test_get_pattern_analytics(self, client: TestClient, test_db, sample_sensor_data):
        """Test GET /api/analytics/patterns endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create traffic readings across different days and hours
        from models import TrafficReading
        base_time = datetime.utcnow() - timedelta(days=3)
        
        for day in range(3):
            for hour in range(0, 24, 4):  # Every 4 hours
                reading = TrafficReading(
                    sensor_id=sensor.id,
                    speed=50 + hour,  # Vary speed by hour
                    volume=100 + day*20,  # Vary volume by day
                    density=15,
                    occupancy=0.8,
                    timestamp=base_time + timedelta(days=day, hours=hour)
                )
                test_db.add(reading)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/analytics/patterns?days=4")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "metric_name" in data
        assert data["metric_name"] == "traffic_patterns"
        assert "data_points" in data
        
        # Should have both hourly and daily patterns
        data_points = data["data_points"]
        hourly_points = [p for p in data_points if p.get("type") == "hourly"]
        daily_points = [p for p in data_points if p.get("type") == "daily"]
        
        assert len(hourly_points) > 0
        assert len(daily_points) > 0
    
    def test_get_trend_analytics(self, client: TestClient, test_db, sample_sensor_data):
        """Test GET /api/analytics/trends endpoint"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        # Create traffic readings with trending data
        from models import TrafficReading
        base_time = datetime.utcnow() - timedelta(days=10)
        
        for day in range(10):
            # Create increasing trend in speed
            reading = TrafficReading(
                sensor_id=sensor.id,
                speed=40 + day*2,  # Increasing speed trend
                volume=150 - day*5,  # Decreasing volume trend
                density=15,
                occupancy=0.8,
                timestamp=base_time + timedelta(days=day)
            )
            test_db.add(reading)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/analytics/trends?days=12")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "metric_name" in data
        assert data["metric_name"] == "traffic_trends"
        assert "summary" in data
        
        summary = data["summary"]
        assert "speed_trend" in summary
        assert "volume_trend" in summary
        
        # Should detect the trends we created
        assert summary["speed_trend"] == "increasing"
        assert summary["volume_trend"] == "decreasing"


class TestModelMetricsEndpoints:
    """Test cases for model metrics endpoints"""
    
    def test_get_model_metrics(self, client: TestClient, test_db):
        """Test GET /api/models/metrics endpoint"""
        # Create test model metrics
        metrics = [
            ModelMetric(
                model_version="v1.0.0",
                metric_name="rmse",
                metric_value=12.5,
                evaluation_timestamp=datetime.utcnow() - timedelta(days=1)
            ),
            ModelMetric(
                model_version="v1.0.0",
                metric_name="mae",
                metric_value=8.3,
                evaluation_timestamp=datetime.utcnow() - timedelta(days=1)
            )
        ]
        
        for metric in metrics:
            test_db.add(metric)
        test_db.commit()
        
        # Test endpoint
        response = client.get("/api/models/metrics")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        
        metric = data[0]
        assert "model_version" in metric
        assert "metric_name" in metric
        assert "metric_value" in metric