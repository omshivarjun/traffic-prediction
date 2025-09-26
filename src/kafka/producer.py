"""
Kafka Producer for Traffic Analytics (Task 3.4)
Streams traffic data to Kafka topics with Python kafka-python client

Features:
- Kafka producer with configurable connection
- Message serialization and delivery confirmation
- Test functionality for Task 3.4 validation
- Production-ready traffic data streaming
"""

from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import csv
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrafficDataProducer:
    """Kafka producer for streaming traffic sensor data"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Kafka producer with configuration"""
        self.config = config or {
            'bootstrap_servers': ['localhost:9092'],
            'value_serializer': lambda x: json.dumps(x).encode('utf-8'),
            'key_serializer': lambda x: x.encode('utf-8') if x else None,
            'acks': 'all',
            'retries': 3,
            'batch_size': 16384,
            'linger_ms': 10,
            'buffer_memory': 33554432
        }
        self.producer: Optional[KafkaProducer] = None
        
    def initialize(self) -> bool:
        """Initialize Kafka producer connection"""
        try:
            self.producer = KafkaProducer(**self.config)
            logger.info("Kafka producer initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            return False
            
    def send_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        """Send a single message to Kafka topic"""
        if not self.producer:
            logger.error("Producer not initialized")
            return False
            
        try:
            future = self.producer.send(topic, value=message, key=key)
            # Wait for the message to be sent (synchronous for testing)
            record_metadata = future.get(timeout=10)
            logger.info(f"Message sent to {record_metadata.topic} partition {record_metadata.partition} at offset {record_metadata.offset}")
            return True
        except KafkaError as e:
            logger.error(f"Failed to send message: {e}")
            return False
            
    def send_test_messages(self, topic: str = 'test', count: int = 5) -> bool:
        """Send test messages for Task 3.4 validation"""
        logger.info(f"Sending {count} test messages to topic '{topic}'")
        
        success_count = 0
        for i in range(count):
            test_message = {
                'message_id': i + 1,
                'timestamp': datetime.now().isoformat(),
                'content': f'Test message {i + 1} for Task 3.4',
                'producer': 'traffic-data-producer',
                'task': 'Task 3.4 - Kafka Python Client Setup'
            }
            
            if self.send_message(topic, test_message, key=f'test-{i+1}'):
                success_count += 1
                logger.info(f"✅ Test message {i+1} sent successfully")
            else:
                logger.error(f"❌ Failed to send test message {i+1}")
                
            time.sleep(0.5)  # Small delay between messages
            
        logger.info(f"Test completed: {success_count}/{count} messages sent successfully")
        return success_count == count
        
    def stream_traffic_data(self, csv_file_path: str, topic: str = 'raw-traffic-events'):
        """Stream traffic data from CSV to Kafka topics"""
        if not self.producer:
            logger.error("Producer not initialized")
            return
            
        try:
            with open(csv_file_path, 'r') as file:
                csv_reader = csv.DictReader(file)
                message_count = 0
                
                for row in csv_reader:
                    # Convert CSV row to traffic event format
                    traffic_event = {
                        'event_id': f"event_{message_count}",
                        'timestamp': datetime.now().isoformat(),
                        'segment_id': row.get('segment_id', 'unknown'),
                        'speed': float(row.get('speed', 0)),
                        'volume': int(row.get('volume', 0)),
                        'occupancy': float(row.get('occupancy', 0)),
                        'coordinates': {
                            'latitude': float(row.get('latitude', 0)),
                            'longitude': float(row.get('longitude', 0))
                        }
                    }
                    
                    if self.send_message(topic, traffic_event, key=traffic_event['segment_id']):
                        message_count += 1
                        if message_count % 100 == 0:
                            logger.info(f"Streamed {message_count} traffic events")
                            
                logger.info(f"Streaming completed: {message_count} events sent to {topic}")
                
        except FileNotFoundError:
            logger.error(f"CSV file not found: {csv_file_path}")
        except Exception as e:
            logger.error(f"Error streaming traffic data: {e}")
            
    def flush(self):
        """Flush any pending messages"""
        if self.producer:
            self.producer.flush()
            
    def shutdown(self):
        """Gracefully shutdown the producer"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer closed")


def test_kafka_connection(bootstrap_servers: str = 'localhost:9092') -> bool:
    """Test Kafka connection for Task 3.4 validation"""
    logger.info("=== Task 3.4: Testing Kafka Python Producer ===")
    
    config = {
        'bootstrap_servers': [bootstrap_servers],
        'value_serializer': lambda x: json.dumps(x).encode('utf-8'),
        'key_serializer': lambda x: x.encode('utf-8') if x else None,
        'acks': 'all',
        'retries': 3
    }
    
    producer = TrafficDataProducer(config)
    
    # Test initialization
    if not producer.initialize():
        logger.error("❌ Task 3.4 FAILED: Could not initialize Kafka producer")
        return False
        
    logger.info("✅ Kafka producer initialized successfully")
    
    # Test message sending
    if producer.send_test_messages():
        logger.info("✅ Task 3.4 PASSED: Python producer working correctly")
        result = True
    else:
        logger.error("❌ Task 3.4 FAILED: Could not send test messages")
        result = False
        
    producer.shutdown()
    return result


if __name__ == "__main__":
    import sys
    
    # Check if running as test
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Task 3.4 test mode
        bootstrap_server = sys.argv[2] if len(sys.argv) > 2 else 'localhost:9092'
        success = test_kafka_connection(bootstrap_server)
        sys.exit(0 if success else 1)
    else:
        # Production mode - example usage
        producer = TrafficDataProducer()
        if producer.initialize():
            # Send test messages
            producer.send_test_messages()
            producer.shutdown()
        else:
            logger.error("Failed to initialize producer")