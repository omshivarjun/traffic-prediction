"""
Integration tests for WebSocket functionality
"""
import pytest
import asyncio
import json
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import WebSocket

from models import Sensor, TrafficReading


class TestWebSocketEndpoints:
    """Test cases for WebSocket endpoints"""
    
    def test_websocket_connection(self, client: TestClient):
        """Test basic WebSocket connection"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Should receive welcome message
            data = websocket.receive_json()
            assert data["type"] == "welcome"
            assert "connection_id" in data
    
    def test_websocket_subscription(self, client: TestClient):
        """Test WebSocket subscription functionality"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Receive welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "welcome"
            
            # Subscribe to traffic data
            subscribe_message = {
                "type": "subscribe",
                "subscription": "traffic_data"
            }
            websocket.send_json(subscribe_message)
            
            # Should receive confirmation
            response = websocket.receive_json()
            assert response["type"] == "subscription_confirmed"
            assert response["subscription"] == "traffic_data"
    
    def test_websocket_unsubscribe(self, client: TestClient):
        """Test WebSocket unsubscribe functionality"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Subscribe first
            websocket.send_json({
                "type": "subscribe",
                "subscription": "traffic_data"
            })
            websocket.receive_json()  # subscription confirmed
            
            # Then unsubscribe
            unsubscribe_message = {
                "type": "unsubscribe",
                "subscription": "traffic_data"
            }
            websocket.send_json(unsubscribe_message)
            
            # Should receive confirmation
            response = websocket.receive_json()
            assert response["type"] == "subscription_cancelled"
            assert response["subscription"] == "traffic_data"
    
    def test_websocket_multiple_subscriptions(self, client: TestClient):
        """Test multiple WebSocket subscriptions"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Subscribe to multiple streams
            subscriptions = ["traffic_data", "predictions", "alerts"]
            
            for sub in subscriptions:
                websocket.send_json({
                    "type": "subscribe",
                    "subscription": sub
                })
                response = websocket.receive_json()
                assert response["type"] == "subscription_confirmed"
                assert response["subscription"] == sub
    
    def test_websocket_heartbeat(self, client: TestClient):
        """Test WebSocket heartbeat mechanism"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Wait for ping message (this would require time-based testing)
            # For now, test pong response
            websocket.send_json({"type": "pong"})
            
            # Should not receive any error or disconnection
            # This is more of a connection stability test
    
    def test_websocket_invalid_message(self, client: TestClient):
        """Test WebSocket error handling for invalid messages"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Send invalid message
            websocket.send_json({
                "type": "invalid_type",
                "data": "test"
            })
            
            # Should receive error message
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "message" in response
    
    def test_websocket_status_request(self, client: TestClient):
        """Test WebSocket status request"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Request status
            websocket.send_json({"type": "get_status"})
            
            # Should receive status response
            response = websocket.receive_json()
            assert response["type"] == "system_status"
            assert "status" in response
            assert "connections" in response
            assert "uptime" in response


class TestWebSocketIntegration:
    """Integration tests for WebSocket with real data"""
    
    def test_websocket_traffic_data_broadcast(self, client: TestClient, test_db, sample_sensor_data, mock_kafka_streamers):
        """Test WebSocket broadcasting of traffic data"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        test_db.refresh(sensor)
        
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Subscribe to traffic data
            websocket.send_json({
                "type": "subscribe",
                "subscription": "traffic_data"
            })
            websocket.receive_json()  # subscription confirmed
            
            # Simulate traffic data update
            # In a real scenario, this would be triggered by Kafka
            traffic_data = {
                "sensor_id": sensor.sensor_id,
                "speed": 45.5,
                "volume": 125,
                "density": 16.2,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # This would normally be handled by the Kafka streamer
            # For testing, we would need to mock the broadcast mechanism
    
    def test_websocket_prediction_broadcast(self, client: TestClient, test_db, sample_sensor_data, mock_kafka_streamers):
        """Test WebSocket broadcasting of predictions"""
        # Create test sensor
        sensor = Sensor(**sample_sensor_data)
        test_db.add(sensor)
        test_db.commit()
        
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Subscribe to predictions
            websocket.send_json({
                "type": "subscribe",
                "subscription": "predictions"
            })
            websocket.receive_json()  # subscription confirmed
            
            # Simulate prediction update
            prediction_data = {
                "sensor_id": sensor.sensor_id,
                "predicted_speed": 42.0,
                "predicted_volume": 135,
                "confidence_score": 0.89,
                "prediction_horizon_minutes": 30,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # This would be broadcast through the WebSocket manager
    
    def test_websocket_concurrent_connections(self, client: TestClient):
        """Test multiple concurrent WebSocket connections"""
        connections = []
        
        try:
            # Create multiple connections
            for i in range(5):
                ws = client.websocket_connect("/ws/real-time")
                ws.__enter__()
                connections.append(ws)
                
                # Each should receive welcome message
                welcome = ws.receive_json()
                assert welcome["type"] == "welcome"
                assert welcome["connection_id"] != ""
            
            # Test that all connections are independent
            for i, ws in enumerate(connections):
                ws.send_json({
                    "type": "subscribe",
                    "subscription": f"traffic_data_{i}"
                })
        
        finally:
            # Clean up connections
            for ws in connections:
                try:
                    ws.__exit__(None, None, None)
                except:
                    pass
    
    def test_websocket_connection_cleanup(self, client: TestClient):
        """Test proper connection cleanup on disconnect"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            welcome = websocket.receive_json()
            connection_id = welcome["connection_id"]
            
            # Subscribe to data
            websocket.send_json({
                "type": "subscribe",
                "subscription": "traffic_data"
            })
            websocket.receive_json()  # subscription confirmed
        
        # Connection should be cleaned up automatically
        # This would require integration with the WebSocket manager
        # to verify the connection is removed from active connections


class TestWebSocketPerformance:
    """Performance tests for WebSocket functionality"""
    
    def test_websocket_message_throughput(self, client: TestClient):
        """Test WebSocket message handling throughput"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Send many subscription requests rapidly
            import time
            start_time = time.time()
            
            for i in range(100):
                websocket.send_json({
                    "type": "subscribe",
                    "subscription": f"test_stream_{i % 5}"
                })
                
                if i < 5:  # Only expect confirmations for unique subscriptions
                    response = websocket.receive_json()
                    assert response["type"] == "subscription_confirmed"
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Should handle messages efficiently
            assert duration < 5.0  # Should complete within 5 seconds
    
    def test_websocket_large_message_handling(self, client: TestClient):
        """Test WebSocket handling of large messages"""
        with client.websocket_connect("/ws/real-time") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Send a large status request
            large_message = {
                "type": "get_status",
                "metadata": {
                    "client_info": "x" * 1000,  # Large metadata
                    "request_id": "test_large_message"
                }
            }
            
            websocket.send_json(large_message)
            
            # Should still receive proper response
            response = websocket.receive_json()
            assert response["type"] == "system_status"