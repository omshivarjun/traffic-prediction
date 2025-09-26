#!/usr/bin/env python3
"""
Docker-based METR-LA Pipeline Producer
Uses Docker exec to send data directly to Kafka container to bypass networking issues
"""

import logging
import json
import csv
import time
import argparse
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metr_la_docker_producer")

class MetrLADockerProducer:
    """Docker-based Kafka producer for METR-LA traffic pipeline"""
    
    def __init__(self, container_name: str = "kafka-broker1", topic: str = "traffic-events"):
        self.container_name = container_name
        self.topic = topic
        self.sent_count = 0
        self.error_count = 0
        
    def test_connection(self) -> bool:
        """Test Kafka connection via Docker"""
        try:
            cmd = [
                "docker", "exec", self.container_name,
                "kafka-topics", "--bootstrap-server", "localhost:9092",
                "--list"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and self.topic in result.stdout:
                logger.info("✅ Kafka connection successful")
                logger.info(f"✅ Topic '{self.topic}' exists")
                return True
            else:
                logger.error(f"❌ Topic '{self.topic}' not found")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def send_batch(self, records: list) -> bool:
        """Send batch of records via Docker console producer"""
        try:
            # Create temporary file with JSON records
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                for record in records:
                    f.write(json.dumps(record) + '\n')
                temp_file = f.name
            
            # Copy file to container
            copy_cmd = ["docker", "cp", temp_file, f"{self.container_name}:/tmp/batch.json"]
            copy_result = subprocess.run(copy_cmd, capture_output=True, text=True)
            
            if copy_result.returncode != 0:
                logger.error(f"Failed to copy file to container: {copy_result.stderr}")
                return False
            
            # Send via console producer
            producer_cmd = [
                "docker", "exec", self.container_name,
                "bash", "-c",
                f"cat /tmp/batch.json | kafka-console-producer --bootstrap-server localhost:9092 --topic {self.topic}"
            ]
            
            producer_result = subprocess.run(producer_cmd, capture_output=True, text=True, timeout=30)
            
            # Cleanup
            cleanup_cmd = ["docker", "exec", self.container_name, "rm", "/tmp/batch.json"]
            subprocess.run(cleanup_cmd, capture_output=True)
            Path(temp_file).unlink()
            
            if producer_result.returncode == 0:
                self.sent_count += len(records)
                return True
            else:
                logger.error(f"Producer failed: {producer_result.stderr}")
                self.error_count += len(records)
                return False
                
        except Exception as e:
            logger.error(f"Error sending batch: {e}")
            self.error_count += len(records)
            return False
    
    def transform_record(self, row: Dict) -> Optional[Dict]:
        """Transform CSV row to pipeline event format"""
        try:
            # Validate required fields
            required_fields = ['timestamp', 'sensor_id', 'speed_mph', 'latitude', 'longitude']
            if not all(key in row for key in required_fields):
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
    
    def stream_csv_file(self, csv_file: str, max_records: Optional[int] = None, 
                       batch_size: int = 100) -> bool:
        """Stream CSV file to Kafka via Docker"""
        
        try:
            csv_path = Path(csv_file)
            if not csv_path.exists():
                logger.error(f"❌ CSV file not found: {csv_file}")
                return False
            
            logger.info(f"🚀 Starting Docker-based pipeline streaming: {csv_file}")
            logger.info(f"   Topic: {self.topic}")
            logger.info(f"   Container: {self.container_name}")
            logger.info(f"   Batch size: {batch_size:,}")
            if max_records:
                logger.info(f"   Max records: {max_records:,}")
            
            start_time = time.time()
            processed_count = 0
            batch = []
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    if max_records and processed_count >= max_records:
                        break
                    
                    # Transform record
                    event = self.transform_record(row)
                    if event:
                        batch.append(event)
                    
                    processed_count += 1
                    
                    # Send batch when full
                    if len(batch) >= batch_size:
                        if self.send_batch(batch):
                            logger.info(f"📤 Sent batch of {len(batch)} records (total: {self.sent_count})")
                        batch = []
                    
                    # Progress logging
                    if processed_count % 1000 == 0:
                        logger.info(f"📊 Processed {processed_count:,} records")
                
                # Send remaining records
                if batch:
                    if self.send_batch(batch):
                        logger.info(f"📤 Sent final batch of {len(batch)} records")
            
            duration = time.time() - start_time
            
            logger.info("🎉 Pipeline streaming completed!")
            logger.info(f"   Total records processed: {processed_count:,}")
            logger.info(f"   Records sent to Kafka: {self.sent_count:,}")
            logger.info(f"   Errors: {self.error_count:,}")
            logger.info(f"   Duration: {duration:.1f} seconds")
            logger.info(f"   Average rate: {self.sent_count/duration:.1f} records/sec")
            
            return self.error_count == 0
            
        except Exception as e:
            logger.error(f"❌ Pipeline streaming failed: {e}")
            return False

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='METR-LA Docker Pipeline Producer')
    parser.add_argument('--csv-file', help='Path to METR-LA CSV file')
    parser.add_argument('--container', default='kafka-broker1', help='Kafka container name')
    parser.add_argument('--topic', default='traffic-events', help='Kafka topic')
    parser.add_argument('--max-records', type=int, help='Maximum records to process')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for sending')
    parser.add_argument('--test-connection', action='store_true', help='Only test connection')
    
    args = parser.parse_args()
    
    producer = MetrLADockerProducer(
        container_name=args.container,
        topic=args.topic
    )
    
    if args.test_connection:
        success = producer.test_connection()
        return 0 if success else 1
    
    if not args.csv_file:
        logger.error("❌ --csv-file is required when not just testing connection")
        return 1
    
    # Test connection first
    if not producer.test_connection():
        logger.error("❌ Connection test failed, exiting")
        return 1
    
    # Stream the file
    success = producer.stream_csv_file(
        csv_file=args.csv_file,
        max_records=args.max_records,
        batch_size=args.batch_size
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())