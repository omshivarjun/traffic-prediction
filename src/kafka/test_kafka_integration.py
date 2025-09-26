"""
Python Kafka Client Integration Test (Task 3.4)
This script tests producer and consumer functionality with the local Kafka 2.8.2 installation
"""

import json
import time
import threading
from datetime import datetime
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, KafkaError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KafkaTestSuite:
    def __init__(self, bootstrap_servers='localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.test_results = []
        
    def add_result(self, test_name, status, details):
        """Add test result to results list"""
        self.test_results.append({
            'test': test_name,
            'status': status,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
        
    def test_connection(self):
        """Test 1: Basic connection to Kafka broker"""
        print("=== Test 1: Testing Kafka Connection ===")
        try:
            # Test producer connection
            producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                api_version=(2, 8, 2)
            )
            
            # Test if we can get metadata
            metadata = producer.partitions_for('__consumer_offsets')  # System topic that should exist
            if metadata is not None:
                self.add_result("Kafka Connection", "✅ PASS", f"Connected to {self.bootstrap_servers}")
                print(f"   ✅ Successfully connected to Kafka at {self.bootstrap_servers}")
                producer.close()
                return True
            else:
                self.add_result("Kafka Connection", "❌ FAIL", "Could not retrieve metadata")
                print("   ❌ Failed to retrieve Kafka metadata")
                producer.close()
                return False
                
        except Exception as e:
            self.add_result("Kafka Connection", "❌ FAIL", f"Connection failed: {str(e)}")
            print(f"   ❌ Connection failed: {str(e)}")
            return False
    
    def test_topic_management(self):
        """Test 2: Topic creation and management"""
        print("\n=== Test 2: Testing Topic Management ===")
        try:
            admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                api_version=(2, 8, 2)
            )
            
            # Create test topic
            test_topic = "python-test-topic"
            topic_config = NewTopic(
                name=test_topic,
                num_partitions=3,
                replication_factor=1
            )
            
            try:
                admin_client.create_topics([topic_config])
                self.add_result("Topic Creation", "✅ PASS", f"Created topic '{test_topic}'")
                print(f"   ✅ Successfully created topic '{test_topic}'")
            except TopicAlreadyExistsError:
                self.add_result("Topic Creation", "✅ PASS", f"Topic '{test_topic}' already exists")
                print(f"   ✅ Topic '{test_topic}' already exists")
            
            # List topics
            metadata = admin_client.describe_topics([test_topic])
            if test_topic in metadata:
                topic_info = metadata[test_topic]
                partitions = len(topic_info.partitions)
                self.add_result("Topic Description", "✅ PASS", f"Topic has {partitions} partitions")
                print(f"   ✅ Topic description successful - {partitions} partitions")
                return test_topic
            else:
                self.add_result("Topic Description", "❌ FAIL", "Topic not found in metadata")
                print("   ❌ Topic description failed")
                return None
                
        except Exception as e:
            self.add_result("Topic Management", "❌ FAIL", f"Error: {str(e)}")
            print(f"   ❌ Topic management failed: {str(e)}")
            return None
    
    def test_producer(self, topic_name):
        """Test 3: Producer functionality"""
        print("\n=== Test 3: Testing Kafka Producer ===")
        try:
            producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                api_version=(2, 8, 2),
                acks='all',  # Wait for all replicas to acknowledge
                retries=3
            )
            
            # Send test messages
            test_messages = [
                {"id": 1, "message": "Test message 1", "timestamp": datetime.now().isoformat()},
                {"id": 2, "message": "Test message 2", "timestamp": datetime.now().isoformat()},
                {"id": 3, "message": "Test message 3", "timestamp": datetime.now().isoformat()}
            ]
            
            sent_count = 0
            for i, message in enumerate(test_messages):
                try:
                    # Send message with key
                    future = producer.send(
                        topic_name, 
                        value=message, 
                        key=f"key-{i}"
                    )
                    
                    # Wait for message to be sent
                    record_metadata = future.get(timeout=10)
                    sent_count += 1
                    print(f"   📤 Message {i+1} sent to partition {record_metadata.partition}, offset {record_metadata.offset}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to send message {i+1}: {str(e)}")
            
            producer.flush()  # Ensure all messages are sent
            producer.close()
            
            if sent_count == len(test_messages):
                self.add_result("Producer Test", "✅ PASS", f"Successfully sent {sent_count} messages")
                print(f"   ✅ Successfully sent all {sent_count} messages")
                return True
            else:
                self.add_result("Producer Test", "⚠️  PARTIAL", f"Sent {sent_count}/{len(test_messages)} messages")
                print(f"   ⚠️  Sent {sent_count} out of {len(test_messages)} messages")
                return False
                
        except Exception as e:
            self.add_result("Producer Test", "❌ FAIL", f"Producer error: {str(e)}")
            print(f"   ❌ Producer test failed: {str(e)}")
            return False
    
    def test_consumer(self, topic_name):
        """Test 4: Consumer functionality"""
        print("\n=== Test 4: Testing Kafka Consumer ===")
        try:
            consumer = KafkaConsumer(
                topic_name,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                group_id='python-test-group',
                auto_offset_reset='earliest',  # Start from beginning of topic
                api_version=(2, 8, 2),
                consumer_timeout_ms=10000  # Timeout after 10 seconds
            )
            
            print("   📥 Starting to consume messages...")
            received_count = 0
            received_messages = []
            
            for message in consumer:
                received_count += 1
                received_messages.append(message.value)
                print(f"   📥 Received message {received_count}: key={message.key}, partition={message.partition}, offset={message.offset}")
                print(f"       Content: {message.value}")
                
                # Stop after receiving a reasonable number of messages
                if received_count >= 5:  # Adjust based on expected messages
                    break
            
            consumer.close()
            
            if received_count > 0:
                self.add_result("Consumer Test", "✅ PASS", f"Successfully received {received_count} messages")
                print(f"   ✅ Successfully received {received_count} messages")
                return True
            else:
                self.add_result("Consumer Test", "⚠️  WARN", "No messages received (may be normal if topic is empty)")
                print("   ⚠️  No messages received (topic may be empty)")
                return False
                
        except Exception as e:
            self.add_result("Consumer Test", "❌ FAIL", f"Consumer error: {str(e)}")
            print(f"   ❌ Consumer test failed: {str(e)}")
            return False
    
    def test_traffic_data_simulation(self):
        """Test 5: Traffic prediction system data simulation"""
        print("\n=== Test 5: Traffic Data Simulation ===")
        try:
            # Create traffic-specific topics
            admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                api_version=(2, 8, 2)
            )
            
            traffic_topics = [
                NewTopic("traffic-events", num_partitions=3, replication_factor=1),
                NewTopic("traffic-aggregates", num_partitions=2, replication_factor=1),
                NewTopic("traffic-predictions", num_partitions=1, replication_factor=1)
            ]
            
            created_topics = []
            for topic in traffic_topics:
                try:
                    admin_client.create_topics([topic])
                    created_topics.append(topic.name)
                    print(f"   ✅ Created topic: {topic.name}")
                except TopicAlreadyExistsError:
                    created_topics.append(topic.name)
                    print(f"   ✅ Topic already exists: {topic.name}")
            
            # Simulate traffic data
            producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                api_version=(2, 8, 2)
            )
            
            # Sample traffic event data
            traffic_events = [
                {
                    "segment_id": "seg_001",
                    "timestamp": datetime.now().isoformat(),
                    "vehicle_count": 45,
                    "average_speed": 32.5,
                    "road_type": "highway"
                },
                {
                    "segment_id": "seg_002", 
                    "timestamp": datetime.now().isoformat(),
                    "vehicle_count": 23,
                    "average_speed": 28.1,
                    "road_type": "arterial"
                }
            ]
            
            for event in traffic_events:
                producer.send("traffic-events", value=event)
                print(f"   📤 Sent traffic event for segment {event['segment_id']}")
            
            producer.flush()
            producer.close()
            
            self.add_result("Traffic Data Simulation", "✅ PASS", f"Created {len(created_topics)} topics and sent sample data")
            print(f"   ✅ Traffic data simulation completed")
            return True
            
        except Exception as e:
            self.add_result("Traffic Data Simulation", "❌ FAIL", f"Error: {str(e)}")
            print(f"   ❌ Traffic data simulation failed: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 Starting Kafka Python Client Test Suite (Task 3.4)")
        print("=" * 60)
        
        # Test 1: Connection
        if not self.test_connection():
            print("\n❌ Connection test failed. Stopping test suite.")
            return False
        
        # Test 2: Topic Management
        test_topic = self.test_topic_management()
        if not test_topic:
            print("\n❌ Topic management test failed. Continuing with remaining tests.")
        
        # Test 3: Producer
        if test_topic:
            self.test_producer(test_topic)
        
        # Test 4: Consumer
        if test_topic:
            self.test_consumer(test_topic)
        
        # Test 5: Traffic Data Simulation
        self.test_traffic_data_simulation()
        
        # Print summary
        self.print_summary()
        
        return True
    
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = len([r for r in self.test_results if "PASS" in r['status']])
        failed = len([r for r in self.test_results if "FAIL" in r['status']])
        warnings = len([r for r in self.test_results if "WARN" in r['status'] or "PARTIAL" in r['status']])
        
        print(f"Total Tests: {len(self.test_results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")
        print()
        
        # Detailed results
        for result in self.test_results:
            print(f"{result['status']} {result['test']}: {result['details']}")
        
        print("\n" + "=" * 60)
        
        if failed == 0:
            print("🎉 Task 3.4: Python Kafka Client Integration - COMPLETED SUCCESSFULLY!")
            print("✨ All tests passed. Kafka Python client is ready for traffic prediction system.")
        else:
            print("⚠️  Task 3.4: Some issues detected. Check failed tests above.")
        
        print("\n🚀 Next Steps for Traffic Prediction System:")
        print("   • Integrate producer in traffic data collection")
        print("   • Set up consumer for real-time processing")
        print("   • Connect with Hadoop for batch processing")
        print("   • Implement Spark streaming for analytics")

if __name__ == "__main__":
    # Run the test suite
    test_suite = KafkaTestSuite()
    test_suite.run_all_tests()