"""
Kafka Consumer Service
Consumes processed traffic events from Kafka and writes them to PostgreSQL
"""

import asyncio
import json
import logging
from typing import Dict, Optional
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from sqlalchemy import text

from src.api.database import db_manager

logger = logging.getLogger(__name__)

class KafkaToDBConsumer:
    """Consumes from Kafka topics and writes to PostgreSQL"""
    
    def __init__(self, bootstrap_servers: str = 'kafka-broker1:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.consumer: Optional[KafkaConsumer] = None
        self.running = False
        self.topic = 'traffic-events'
        
    async def start(self):
        """Start the Kafka consumer"""
        try:
            # Initialize Kafka consumer
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id='backend-db-writer',
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            self.running = True
            logger.info(f"Kafka consumer started, consuming from '{self.topic}'")
            
            # Start consuming in background task
            asyncio.create_task(self._consume_loop())
            
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise
    
    async def stop(self):
        """Stop the Kafka consumer"""
        self.running = False
        if self.consumer:
            self.consumer.close()
        logger.info("Kafka consumer stopped")
    
    async def _consume_loop(self):
        """Main consumption loop"""
        while self.running:
            try:
                # Poll for messages (with timeout to allow graceful shutdown)
                messages = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for record in records:
                        await self._process_message(record.value)
                
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in Kafka consume loop: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _process_message(self, message: Dict):
        """Process a single Kafka message and write to database"""
        try:
            # Handle two message formats:
            # 1. Flat format from stream processor: {sensor_id, timestamp, speed, volume, ...}
            # 2. Nested format from raw events: {sensor_id, timestamp, traffic_data: {speed_mph, ...}}
            
            # Extract timestamp
            timestamp = message.get('timestamp')
            
            # Extract traffic data - check for nested format first
            if 'traffic_data' in message:
                traffic_data = message['traffic_data']
                speed = traffic_data.get('speed_mph')
                volume = traffic_data.get('volume_vehicles_per_hour')
                occupancy = traffic_data.get('occupancy_percentage')
            else:
                # Flat format
                speed = message.get('speed')
                volume = message.get('volume')
                occupancy = message.get('occupancy')
            
            # Validate required fields
            if not all([timestamp, speed]):
                logger.warning(f"Skipping message with missing required fields: {message}")
                return
            
            # Use first sensor UUID as default (TODO: create sensor mapping)
            default_sensor_uuid = '444a7781-5c75-4fed-9d6b-e50c99d8661c'  # SENSOR_001
            
            # Insert into database with correct column names
            async with db_manager.async_session_scope() as session:
                query = text("""
                    INSERT INTO traffic.traffic_readings (
                        sensor_id, timestamp, speed, volume, occupancy, created_at
                    ) VALUES (
                        :sensor_id, TO_TIMESTAMP(:timestamp, 'YYYY-MM-DD"T"HH24:MI:SS'), 
                        :speed, :volume, :occupancy, NOW()
                    )
                """)
                
                await session.execute(query, {
                    'sensor_id': default_sensor_uuid,
                    'timestamp': timestamp,
                    'speed': speed,
                    'volume': volume,
                    'occupancy': occupancy
                })
                
                await session.commit()
                
            logger.debug(f"Inserted traffic reading: time={timestamp}, speed={speed}")
            
        except Exception as e:
            logger.error(f"Error processing Kafka message: {e}, message={message}")

# Global consumer instance
kafka_consumer = KafkaToDBConsumer()
