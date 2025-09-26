"""
Test configuration and fixtures for FastAPI backend testing
"""
import os
import sys
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from testcontainers import DockerContainer
from testcontainers.postgres import PostgresContainer

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app
from database import get_db, DatabaseManager
from models import Base
from config import get_settings

# Test database URL
TEST_DATABASE_URL = "sqlite:///./test_traffic.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for testing"""
    with PostgresContainer("postgres:13") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def test_db_url(postgres_container):
    """Get test database URL from container"""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="function")
def test_engine(test_db_url):
    """Create test database engine"""
    engine = create_engine(
        test_db_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False} if "sqlite" in test_db_url else {}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine) -> Generator[Session, None, None]:
    """Create test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_sensor_data():
    """Sample sensor data for testing"""
    return {
        "sensor_id": "TEST_001",
        "location_name": "Test Highway",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "sensor_type": "loop",
        "status": "active"
    }


@pytest.fixture
def sample_traffic_data():
    """Sample traffic reading data for testing"""
    return {
        "speed": 55.5,
        "volume": 120,
        "density": 15.2,
        "occupancy": 0.85,
        "timestamp": "2024-01-15T10:30:00Z"
    }


@pytest.fixture
def sample_prediction_data():
    """Sample prediction data for testing"""
    return {
        "predicted_speed": 45.0,
        "predicted_volume": 150,
        "predicted_density": 18.5,
        "confidence_score": 0.92,
        "prediction_horizon_minutes": 30,
        "model_version": "v1.0.0"
    }


class MockKafkaStreamer:
    """Mock Kafka streamer for testing"""
    def __init__(self):
        self.is_healthy = True
        self.messages = []
    
    async def send_message(self, message):
        self.messages.append(message)
    
    def health_check(self):
        return self.is_healthy


@pytest.fixture
def mock_kafka_streamers():
    """Mock Kafka streamers for testing"""
    return {
        'traffic': MockKafkaStreamer(),
        'prediction': MockKafkaStreamer(),
        'alert': MockKafkaStreamer()
    }


class MockWebSocketManager:
    """Mock WebSocket manager for testing"""
    def __init__(self):
        self.connections = []
        self.messages = []
    
    async def connect(self, websocket):
        self.connections.append(websocket)
    
    def disconnect(self, websocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
    
    async def broadcast(self, message):
        self.messages.append(message)


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager for testing"""
    return MockWebSocketManager()