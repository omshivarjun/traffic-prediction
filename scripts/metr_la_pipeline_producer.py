#!/usr/bin/env python3
"""
METR-LA Pipeline Producer
Optimized Kafka producer for the complete METR-LA traffic prediction workflow:
CSV → Kafka → Spark → HDFS → ML → Predictions → Visualization

Features:
- Real-time and batch streaming
- Schema Registry integration
- Error handling and metrics
- Docker-optimized for local development
"""

import json
import time
import logging
import argparse
import sys
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

# Kafka imports
from kafka import KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metr_la_pipeline_producer")

class MetrLAPipelineProducer:
    """Optimized Kafka producer for METR-LA traffic pipeline"""
    
    def __init__(self, kafka_config: Dict[str, Any]):
        """Initialize producer with Docker-optimized configuration"""
        self.kafka_config = kafka_config
        self.topic = kafka_config.get('topic', 'traffic-events')
        self.running = False
        
        # Statistics
        self.sent_count = 0
        self.error_count = 0
        self.start_time = None
        
        # Create Kafka producer with optimal settings
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_config.get('bootstrap_servers', 'localhost:9094'),
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas
            retries=3,
            retry_backoff_ms=1000,
            max_in_flight_requests_per_connection=1,
            enable_idempotence=True,
            batch_size=16384,
            linger_ms=10,  # Small linger for better throughput
            compression_type='gzip',
            buffer_memory=33554432,
            request_timeout_ms=30000,
            delivery_timeout_ms=120000
        )
        
        logger.info(f"🚀 Initialized METR-LA Pipeline Producer for topic: {self.topic}")
        logger.info(f"📡 Kafka broker: {kafka_config.get('bootstrap_servers')}")
    
    def test_connection(self) -> bool:
        """Test Kafka connection"""
        try:
            metadata = self.producer.bootstrap_connected()
            if metadata:
                logger.info("✅ Kafka connection successful")
                return True
            else:
                logger.error("❌ Failed to connect to Kafka")
                return False
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def transform_record(self, row: Dict) -> Optional[Dict]:
        """Transform CSV row to pipeline event format"""
        try:
            # Validate required fields
            if not all(key in row for key in ['timestamp', 'sensor_id', 'speed_mph', 'latitude', 'longitude']):
                return None
            
            # Handle missing/invalid speed values
            speed = None
            if row['speed_mph'] is not None and str(row['speed_mph']).strip():
                try:
                    speed_val = float(row['speed_mph'])
                    if 0 <= speed_val <= 120:  # Reasonable speed range
                        speed = speed_val
                except (ValueError, TypeError):
                    pass
            
            # Skip records with no valid speed
            if speed is None:
                return None
            
            # Create traffic event record
            event = {
                'timestamp': str(row['timestamp']),
                'sensor_id': str(row['sensor_id']),
                'speed_mph': speed,
                'latitude': float(row['latitude']),
                'longitude': float(row['longitude']),
                'segment_id': str(row.get('segment_id', f"seg_{row['sensor_id']}")),
                'road_type': str(row.get('road_type', 'unknown')),
                'lane_count': int(row.get('lane_count', 1)),
                'event_id': f"{row['sensor_id']}_{row['timestamp']}",
                'event_time': datetime.now().isoformat(),
                'pipeline_source': 'metr_la_csv'
            }
            
            return event
            
        except Exception as e:
            logger.warning(f"Error transforming record: {e}")
            return None
    
    def send_record(self, record: Dict, key: Optional[str] = None) -> bool:
        """Send single record to Kafka"""
        try:
            # Use sensor_id as partition key for locality
            partition_key = key or record.get('sensor_id', 'unknown')
            
            future = self.producer.send(
                self.topic,
                value=record,
                key=partition_key
            )
            
            # Add success callback
            future.add_callback(self._on_send_success)
            future.add_errback(self._on_send_error)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending record: {e}")
            self.error_count += 1
            return False
    
    def _on_send_success(self, record_metadata):
        """Callback for successful send"""
        self.sent_count += 1
    
    def _on_send_error(self, error):
        """Callback for send error"""
        self.error_count += 1
        logger.error(f"Send error: {error}")
    
    def stream_csv_file(self, csv_file: str, replay_speed: float = 1.0, 
                       max_records: Optional[int] = None, batch_size: int = 1000) -> bool:
        """Stream METR-LA CSV data to Kafka"""
        
        try:
            csv_path = Path(csv_file)
            if not csv_path.exists():
                logger.error(f"❌ CSV file not found: {csv_file}")
                return False
            
            logger.info(f"🚀 Starting pipeline streaming: {csv_file}")
            logger.info(f"   Topic: {self.topic}")
            logger.info(f"   Replay speed: {replay_speed}x (0 = as fast as possible)")
            logger.info(f"   Batch size: {batch_size:,}")
            if max_records:
                logger.info(f"   Max records: {max_records:,}")
            
            self.running = True
            self.start_time = time.time()
            record_count = 0
            batch_count = 0
            
            # Read CSV in chunks for large files
            chunk_size = 10000
            previous_timestamp = None
            
            for chunk_df in pd.read_csv(csv_path, chunksize=chunk_size):
                if not self.running:
                    break
                
                # Convert timestamp column to datetime
                chunk_df['timestamp'] = pd.to_datetime(chunk_df['timestamp'])
                
                # Sort by timestamp for proper replay
                chunk_df = chunk_df.sort_values('timestamp')
                
                # Process records in the chunk
                batch_records = []
                
                for idx, row in chunk_df.iterrows():
                    if not self.running:
                        break
                    
                    if max_records and record_count >= max_records:
                        break
                    
                    # Transform record
                    record = self.transform_record(row.to_dict())
                    if not record:
                        continue
                    
                    # Handle replay timing
                    if replay_speed > 0 and previous_timestamp is not None:
                        current_timestamp = pd.to_datetime(record['timestamp'])
                        time_diff = (current_timestamp - previous_timestamp).total_seconds()
                        sleep_time = time_diff / replay_speed
                        
                        if sleep_time > 0:
                            time.sleep(min(sleep_time, 0.1))  # Cap sleep at 100ms
                    
                    # Add to batch
                    batch_records.append(record)
                    
                    # Send batch when full
                    if len(batch_records) >= batch_size:
                        self._send_batch(batch_records)
                        batch_records = []
                        batch_count += 1
                        
                        # Progress reporting
                        if batch_count % 10 == 0:
                            elapsed = time.time() - self.start_time
                            rate = self.sent_count / elapsed if elapsed > 0 else 0
                            logger.info(f"📊 Batch {batch_count}: {self.sent_count:,} records sent "
                                      f"({rate:.1f} records/sec, {self.error_count} errors)")
                    
                    record_count += 1
                    if record['timestamp']:
                        previous_timestamp = pd.to_datetime(record['timestamp'])
                
                # Send remaining records in batch
                if batch_records:
                    self._send_batch(batch_records)
                    batch_count += 1
            
            # Final flush
            self.producer.flush(timeout=30)
            
            # Summary
            elapsed = time.time() - self.start_time
            avg_rate = self.sent_count / elapsed if elapsed > 0 else 0
            
            logger.info(f"🎉 Pipeline streaming completed!")
            logger.info(f"   Total records processed: {record_count:,}")
            logger.info(f"   Records sent to Kafka: {self.sent_count:,}")
            logger.info(f"   Errors: {self.error_count}")
            logger.info(f"   Duration: {elapsed:.1f} seconds")
            logger.info(f"   Average rate: {avg_rate:.1f} records/sec")
            logger.info(f"   Batches sent: {batch_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Streaming failed: {e}", exc_info=True)
            return False
        finally:
            self.running = False
    
    def _send_batch(self, batch_records: List[Dict]):
        """Send batch of records"""
        for record in batch_records:
            self.send_record(record)
        
        # Flush periodically
        if len(batch_records) > 0:
            self.producer.flush(timeout=5)
    
    def stop(self):
        """Stop the producer gracefully"""
        logger.info("🛑 Stopping producer...")
        self.running = False
        if self.producer:
            self.producer.flush(timeout=10)
            self.producer.close(timeout=10)
        logger.info("✅ Producer stopped")

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    logger.info("🛑 Received interrupt signal, shutting down...")
    global producer
    if producer:
        producer.stop()
    sys.exit(0)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='METR-LA Pipeline Producer')
    parser.add_argument('--csv-file', required=True, help='Path to METR-LA CSV file')
    parser.add_argument('--kafka-broker', default='localhost:9094', help='Kafka broker address')
    parser.add_argument('--topic', default='traffic-events', help='Kafka topic name')
    parser.add_argument('--replay-speed', type=float, default=10.0, 
                       help='Replay speed multiplier (0 = as fast as possible)')
    parser.add_argument('--max-records', type=int, help='Maximum records to process')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for sending')
    parser.add_argument('--test-connection', action='store_true', help='Test Kafka connection and exit')
    
    args = parser.parse_args()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Kafka configuration
    kafka_config = {
        'bootstrap_servers': args.kafka_broker,
        'topic': args.topic
    }
    
    global producer
    producer = None
    try:
        # Create producer
        producer = MetrLAPipelineProducer(kafka_config)
        
        # Test connection if requested
        if args.test_connection:
            if producer.test_connection():
                logger.info("✅ Kafka connection test successful")
                return 0
            else:
                logger.error("❌ Kafka connection test failed")
                return 1
        
        # Check if CSV file exists
        csv_path = Path(args.csv_file)
        if not csv_path.exists():
            logger.error(f"❌ CSV file not found: {args.csv_file}")
            return 1
        
        # Start streaming
        success = producer.stream_csv_file(
            csv_file=args.csv_file,
            replay_speed=args.replay_speed,
            max_records=args.max_records,
            batch_size=args.batch_size
        )
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"❌ Producer failed: {e}", exc_info=True)
        return 1
    finally:
        if producer:
            producer.stop()

if __name__ == "__main__":
    sys.exit(main())