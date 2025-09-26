#!/usr/bin/env python3
"""
Test script for Traffic Data Producer - Task 8
Validates producer functionality without requiring full Kafka setup.
"""

import os
import sys
import tempfile
import csv
from datetime import datetime, timedelta

# Add producer to path
sys.path.insert(0, os.path.dirname(__file__))

from traffic_producer import (
    ProducerConfig, 
    SensorMetadata, 
    TrafficEvent, 
    TrafficDataProducer,
    ProducerMetrics
)


def create_test_data():
    """Create test CSV files for validation"""
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Create test traffic data CSV
    traffic_data_file = os.path.join(temp_dir, 'test_traffic_data.csv')
    with open(traffic_data_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'sensor_id', 'speed_mph', 'volume_vehicles_per_hour', 
                        'latitude', 'longitude', 'road_type', 'road_name', 'direction'])
        
        # Generate 10 test records with 5-minute intervals
        base_time = datetime(2023, 6, 1, 12, 0, 0)
        for i in range(10):
            timestamp = base_time + timedelta(minutes=i * 5)
            writer.writerow([
                timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                f'TEST_{i:03d}',
                60 + (i * 5),  # Speed from 60-105 mph
                800 + (i * 50),  # Volume from 800-1300 vph
                34.0522 + (i * 0.001),  # Latitude
                -118.2437 - (i * 0.001),  # Longitude
                'Highway',
                f'Test Highway {i}',
                'N' if i % 2 == 0 else 'S'
            ])
    
    # Create test sensor metadata CSV
    metadata_file = os.path.join(temp_dir, 'test_sensor_metadata.csv')
    with open(metadata_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['sensor_id', 'latitude', 'longitude', 'road_type', 
                        'road_name', 'direction', 'lanes', 'installation_date'])
        
        for i in range(10):
            writer.writerow([
                f'TEST_{i:03d}',
                34.0522 + (i * 0.001),
                -118.2437 - (i * 0.001),
                'Highway',
                f'Test Highway {i}',
                'N' if i % 2 == 0 else 'S',
                4,
                '2022-01-01'
            ])
    
    return temp_dir, traffic_data_file, metadata_file


def test_producer_config():
    """Test ProducerConfig initialization"""
    print("Testing ProducerConfig...")
    
    config = ProducerConfig(
        kafka_bootstrap_servers="localhost:9092",
        topic_name="test-topic",
        replay_speed=2.0,
        batch_size=50
    )
    
    assert config.kafka_bootstrap_servers == "localhost:9092"
    assert config.topic_name == "test-topic"
    assert config.replay_speed == 2.0
    assert config.batch_size == 50
    
    print("✓ ProducerConfig test passed")


def test_sensor_metadata():
    """Test SensorMetadata functionality"""
    print("Testing SensorMetadata...")
    
    sensor = SensorMetadata(
        sensor_id="TEST_001",
        latitude=34.0522,
        longitude=-118.2437,
        road_type="Highway",
        road_name="Test Highway",
        direction="N",
        lanes=4,
        installation_date="2022-01-01"
    )
    
    assert sensor.sensor_id == "TEST_001"
    assert sensor.latitude == 34.0522
    assert sensor.lanes == 4
    
    print("✓ SensorMetadata test passed")


def test_producer_metrics():
    """Test ProducerMetrics functionality"""
    print("Testing ProducerMetrics...")
    
    metrics = ProducerMetrics()
    
    # Test initial state
    stats = metrics.get_stats()
    assert stats['messages_sent'] == 0
    assert stats['messages_failed'] == 0
    
    # Test success recording
    metrics.record_success(1000)
    metrics.record_success(1500)
    
    # Test failure recording
    metrics.record_failure()
    
    stats = metrics.get_stats()
    assert stats['messages_sent'] == 2
    assert stats['messages_failed'] == 1
    assert stats['bytes_sent'] == 2500
    
    print("✓ ProducerMetrics test passed")


def test_producer_initialization():
    """Test TrafficDataProducer initialization without Kafka"""
    print("Testing TrafficDataProducer initialization...")
    
    temp_dir, data_file, metadata_file = create_test_data()
    
    try:
        config = ProducerConfig(
            data_file=data_file,
            metadata_file=metadata_file,
            kafka_bootstrap_servers="localhost:9092"
        )
        
        producer = TrafficDataProducer(config)
        
        # Test metadata loading
        producer.load_sensor_metadata()
        assert len(producer.sensor_metadata) == 10
        
        # Test specific sensor
        sensor = producer.sensor_metadata.get('TEST_001')
        assert sensor is not None
        assert sensor.road_name == 'Test Highway 1'
        
        print("✓ TrafficDataProducer initialization test passed")
        
    finally:
        # Cleanup temp files
        import shutil
        shutil.rmtree(temp_dir)


def test_csv_row_conversion():
    """Test CSV row to TrafficEvent conversion"""
    print("Testing CSV row conversion...")
    
    temp_dir, data_file, metadata_file = create_test_data()
    
    try:
        config = ProducerConfig(
            data_file=data_file,
            metadata_file=metadata_file
        )
        
        producer = TrafficDataProducer(config)
        producer.load_sensor_metadata()
        
        # Test row conversion
        test_row = {
            'timestamp': '2023-06-01 12:00:00',
            'sensor_id': 'TEST_001',
            'speed_mph': '60',
            'volume_vehicles_per_hour': '800',
            'latitude': '34.0522',
            'longitude': '-118.2437',
            'road_type': 'Highway',
            'road_name': 'Test Highway 1',
            'direction': 'N'
        }
        
        event = producer.convert_csv_row_to_event(test_row, 1)
        
        assert event.event_id.startswith('EVT_TEST_001_')
        assert event.segment_id.startswith('SEG_TEST_001_')
        assert event.speed is not None
        assert event.speed > 90  # Converted from mph to km/h
        assert event.volume == 800
        assert abs(event.coordinates['latitude'] - 34.0532) < 0.001
        assert event.quality_score > 0
        
        print("✓ CSV row conversion test passed")
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)


def test_config_file_operations():
    """Test configuration file creation and loading"""
    print("Testing configuration file operations...")
    
    from traffic_producer import create_default_config_file, load_config_from_file
    
    temp_dir = tempfile.mkdtemp()
    config_file = os.path.join(temp_dir, 'test_config.ini')
    
    try:
        # Test config file creation
        create_default_config_file(config_file)
        assert os.path.exists(config_file)
        
        # Test config file loading
        config = load_config_from_file(config_file)
        assert config.kafka_bootstrap_servers == 'localhost:9092'
        assert config.topic_name == 'traffic-raw'
        assert config.batch_size == 100
        
        print("✓ Configuration file operations test passed")
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)


def run_all_tests():
    """Run all tests"""
    print("Running Traffic Data Producer Tests...\n")
    
    tests = [
        test_producer_config,
        test_sensor_metadata,
        test_producer_metrics,
        test_producer_initialization,
        test_csv_row_conversion,
        test_config_file_operations
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        print()
    
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)