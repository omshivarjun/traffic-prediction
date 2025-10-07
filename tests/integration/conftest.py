"""
Integration Test Configuration
"""

import os

# Test environment configuration
TEST_CONFIG = {
    'backend_url': os.getenv('TEST_BACKEND_URL', 'http://localhost:8000'),
    'frontend_url': os.getenv('TEST_FRONTEND_URL', 'http://localhost:3002'),
    'kafka_bootstrap_servers': os.getenv('TEST_KAFKA_SERVERS', 'localhost:9094'),
    'database_url': os.getenv('TEST_DATABASE_URL', 'postgresql://postgres:password@localhost:5433/traffic_db'),
}

# Test data configuration
TEST_DATA = {
    'sample_traffic_event': {
        'sensor_id': 'test-sensor-001',
        'timestamp': '2025-10-05T12:00:00Z',
        'speed': 60.5,
        'volume': 1200,
        'occupancy': 0.72
    },
    'sample_sensor': {
        'location': 'Test Highway I-405',
        'sensor_type': 'test_sensor',
        'status': 'active',
        'latitude': 34.0522,
        'longitude': -118.2437
    }
}

# Kafka topic configuration
KAFKA_TOPICS = {
    'input': 'traffic-raw',
    'processed': 'traffic-events',
    'predictions': 'traffic-predictions',
    'alerts': 'traffic-alerts'
}

# Test thresholds
PERFORMANCE_THRESHOLDS = {
    'api_response_time_ms': 200,
    'database_query_time_ms': 100,
    'e2e_latency_ms': 5000,
    'websocket_message_delay_ms': 100
}

# Test timeouts
TEST_TIMEOUTS = {
    'kafka_consumer_timeout_ms': 5000,
    'api_request_timeout_s': 10,
    'database_query_timeout_s': 5,
    'websocket_connection_timeout_s': 5
}
