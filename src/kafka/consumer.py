"""
Kafka Consumer for Traffic Analytics (Task 3.4)
Consumes traffic data from Kafka topics with Python kafka-python client

Features:
- Kafka consumer with configurable connection
- Message deserialization and validation
- Test functionality for Task 3.4 validation
- Consumer group management
"""

from kafka import KafkaConsumer
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import signal
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrafficDataConsumer:
    """Kafka consumer for processing traffic sensor data"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Kafka consumer with configuration"""
        self.config = config or {
            'bootstrap_servers': ['localhost:9092'],
            'auto_offset_reset': 'earliest',
            'enable_auto_commit': True,
            'group_id': 'traffic-analytics-group',
            'value_deserializer': lambda m: json.loads(m.decode('utf-8')) if m else None,
            'key_deserializer': lambda m: m.decode('utf-8') if m else None,
            'consumer_timeout_ms': 10000  # 10 seconds timeout for testing
        }
        self.consumer: Optional[KafkaConsumer] = None
        self.running = False
        
    def initialize(self, topics: List[str]) -> bool:
        """Initialize Kafka consumer connection"""
        try:
            self.consumer = KafkaConsumer(*topics, **self.config)
            logger.info(f"Kafka consumer initialized for topics: {topics}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            return False
            
    def consume_messages(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """Consume messages from subscribed topics"""
        if not self.consumer:
            logger.error("Consumer not initialized")
            return []
            
        messages = []
        message_count = 0
        
        try:
            logger.info(f"Starting to consume messages (max: {max_messages})")
            
            for message in self.consumer:
                if message_count >= max_messages:
                    break
                    
                message_data = {
                    'topic': message.topic,
                    'partition': message.partition,
                    'offset': message.offset,
                    'key': message.key,
                    'value': message.value,
                    'timestamp': message.timestamp,
                    'consumed_at': datetime.now().isoformat()
                }
                
                messages.append(message_data)
                message_count += 1
                
                logger.info(f"✅ Consumed message {message_count}: topic={message.topic}, key={message.key}")
                
        except Exception as e:
            logger.error(f"Error consuming messages: {e}")
            
        logger.info(f"Consumption completed: {len(messages)} messages consumed")
        return messages
        
    def consume_test_messages(self, topic: str = 'test', max_messages: int = 5) -> bool:
        """Consume test messages for Task 3.4 validation"""
        logger.info(f"=== Task 3.4: Testing Kafka Python Consumer ===")
        logger.info(f"Consuming test messages from topic '{topic}'")
        
        if not self.initialize([topic]):
            logger.error("❌ Failed to initialize consumer")
            return False
            
        messages = self.consume_messages(max_messages)
        
        if messages:
            logger.info(f"✅ Task 3.4 PASSED: Successfully consumed {len(messages)} messages")
            
            # Display message details
            for i, msg in enumerate(messages, 1):
                logger.info(f"   Message {i}: {msg['value']}")
                
            return True
        else:
            logger.warning("⚠️  Task 3.4: No messages found in topic (this may be expected if no messages were sent)")
            return False
            
    def consume_traffic_data(self, topics: List[str] = None):
        """Consume and process traffic data from Kafka topics"""
        if topics is None:
            topics = ['raw-traffic-events', 'processed-traffic-aggregates']
            
        if not self.initialize(topics):
            logger.error("Failed to initialize consumer")
            return
            
        logger.info(f"Starting traffic data consumption from topics: {topics}")
        self.running = True
        
        # Set up signal handler for graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            self.running = False
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            message_count = 0
            
            for message in self.consumer:
                if not self.running:
                    break
                    
                # Process traffic data message
                self.process_traffic_message(message)
                message_count += 1
                
                if message_count % 100 == 0:
                    logger.info(f"Processed {message_count} traffic messages")
                    
        except Exception as e:
            logger.error(f"Error in traffic data consumption: {e}")
        finally:
            self.shutdown()
            
    def process_traffic_message(self, message):
        """Process individual traffic data message"""
        try:
            # Extract message data
            topic = message.topic
            data = message.value
            
            if topic == 'raw-traffic-events':
                # Process raw traffic event
                logger.debug(f"Processing raw traffic event: {data.get('event_id', 'unknown')}")
                
            elif topic == 'processed-traffic-aggregates':
                # Process aggregated traffic data
                logger.debug(f"Processing traffic aggregate: {data.get('segment_id', 'unknown')}")
                
            # In a real implementation, this would:
            # - Validate message format
            # - Store data in database
            # - Forward to downstream systems
            # - Update real-time dashboards
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
    def shutdown(self):
        """Gracefully shutdown the consumer"""
        self.running = False
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")


def test_kafka_consumer(bootstrap_servers: str = 'localhost:9092', topic: str = 'test') -> bool:
    """Test Kafka consumer for Task 3.4 validation"""
    
    config = {
        'bootstrap_servers': [bootstrap_servers],
        'auto_offset_reset': 'earliest',
        'enable_auto_commit': True,
        'group_id': 'task-3-4-test-group',
        'value_deserializer': lambda m: json.loads(m.decode('utf-8')) if m else None,
        'key_deserializer': lambda m: m.decode('utf-8') if m else None,
        'consumer_timeout_ms': 5000  # 5 seconds timeout for testing
    }
    
    consumer = TrafficDataConsumer(config)
    
    # Test message consumption
    success = consumer.consume_test_messages(topic)
    
    consumer.shutdown()
    return success


if __name__ == "__main__":
    
    # Check if running as test
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Task 3.4 test mode
        bootstrap_server = sys.argv[2] if len(sys.argv) > 2 else 'localhost:9092'
        topic = sys.argv[3] if len(sys.argv) > 3 else 'test'
        
        success = test_kafka_consumer(bootstrap_server, topic)
        sys.exit(0 if success else 1)
    else:
        # Production mode - example usage
        consumer = TrafficDataConsumer()
        consumer.consume_traffic_data()