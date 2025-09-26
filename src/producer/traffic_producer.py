#!/usr/bin/env python3
"""
Traffic Data Producer Service - Task 8.1
Streams METR-LA traffic data to Kafka topics with configurable replay speed and monitoring.

This service reads METR-LA CSV data and streams it to Kafka topics in real-time simulation.
Provides configurable replay speed, comprehensive monitoring, and robust error handling.
"""

import os
import sys
import json
import csv
import time
import logging
import signal
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socket

import argparse
import configparser
from kafka import KafkaProducer
from kafka.errors import KafkaError


@dataclass
class ProducerConfig:
    """Configuration for the traffic data producer"""
    kafka_bootstrap_servers: str = "localhost:9092"
    topic_name: str = "traffic-raw"
    data_file: str = "data/raw/metr_la_sample_data.csv"
    metadata_file: str = "data/raw/metr_la_sensor_metadata.csv"
    replay_speed: float = 1.0  # 1.0 = real-time, 2.0 = 2x speed, 0.5 = half speed
    batch_size: int = 100
    max_records: Optional[int] = None  # None = unlimited
    loop_data: bool = False  # Loop the dataset when reaching end
    compression_type: str = "snappy"
    acks: str = "1"  # 0=none, 1=leader, all=all replicas
    retries: int = 3
    max_in_flight: int = 5
    linger_ms: int = 100
    buffer_memory: int = 33554432  # 32MB
    log_level: str = "INFO"
    log_file: Optional[str] = None
    health_check_port: int = 8080
    metrics_interval: int = 30  # seconds


@dataclass 
class SensorMetadata:
    """Metadata for a traffic sensor"""
    sensor_id: str
    latitude: float
    longitude: float
    road_type: str
    road_name: str
    direction: str
    lanes: int
    installation_date: str


@dataclass
class TrafficEvent:
    """Traffic event data structure"""
    event_id: str
    segment_id: str
    timestamp: int
    speed: Optional[float]
    volume: Optional[int]
    occupancy: Optional[float]
    coordinates: Dict[str, float]
    source: str
    quality_score: float
    metadata: Dict[str, Any]


class ProducerMetrics:
    """Metrics tracking for the producer"""
    
    def __init__(self):
        self.messages_sent = 0
        self.messages_failed = 0
        self.bytes_sent = 0
        self.start_time = time.time()
        self.last_metrics_time = time.time()
        self.last_message_count = 0
        self.current_throughput = 0.0
        self.lock = threading.Lock()
    
    def record_success(self, message_size: int):
        """Record successful message delivery"""
        with self.lock:
            self.messages_sent += 1
            self.bytes_sent += message_size
    
    def record_failure(self):
        """Record failed message delivery"""
        with self.lock:
            self.messages_failed += 1
    
    def update_throughput(self):
        """Update throughput calculation"""
        with self.lock:
            current_time = time.time()
            time_diff = current_time - self.last_metrics_time
            
            if time_diff >= 1.0:  # Update every second
                message_diff = self.messages_sent - self.last_message_count
                self.current_throughput = message_diff / time_diff
                
                self.last_metrics_time = current_time
                self.last_message_count = self.messages_sent
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics"""
        with self.lock:
            runtime = time.time() - self.start_time
            total_messages = self.messages_sent + self.messages_failed
            
            return {
                "messages_sent": self.messages_sent,
                "messages_failed": self.messages_failed,
                "total_messages": total_messages,
                "bytes_sent": self.bytes_sent,
                "runtime_seconds": runtime,
                "avg_throughput": self.messages_sent / runtime if runtime > 0 else 0,
                "current_throughput": self.current_throughput,
                "success_rate": self.messages_sent / total_messages if total_messages > 0 else 0,
                "failure_rate": self.messages_failed / total_messages if total_messages > 0 else 0
            }


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check and metrics endpoints"""
    
    def __init__(self, producer_instance, *args, **kwargs):
        self.producer = producer_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests for health and metrics"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/health':
            self._handle_health_check()
        elif parsed_path.path == '/metrics':
            self._handle_metrics()
        else:
            self._send_response(404, {'error': 'Not found'})
    
    def _handle_health_check(self):
        """Handle health check endpoint"""
        health_status = {
            'status': 'healthy' if self.producer.running else 'stopped',
            'producer_initialized': self.producer.producer is not None,
            'sensors_loaded': len(self.producer.sensor_metadata),
            'timestamp': int(time.time() * 1000)
        }
        
        # Check Kafka connectivity
        try:
            if self.producer.producer:
                # Simple connectivity test
                health_status['kafka_connected'] = True
            else:
                health_status['kafka_connected'] = False
        except Exception:
            health_status['kafka_connected'] = False
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        self._send_response(status_code, health_status)
    
    def _handle_metrics(self):
        """Handle metrics endpoint"""
        metrics = self.producer.metrics.get_stats()
        self._send_response(200, metrics)
    
    def _send_response(self, status_code: int, data: Dict[str, Any]):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def log_message(self, format, *args):
        """Override to suppress default HTTP logging"""
        pass


class TrafficDataProducer:
    """Main producer class for streaming METR-LA traffic data to Kafka"""
    
    def __init__(self, config: ProducerConfig):
        self.config = config
        self.producer: Optional[KafkaProducer] = None
        self.sensor_metadata: Dict[str, SensorMetadata] = {}
        self.metrics = ProducerMetrics()
        self.logger = self._setup_logging()
        self.running = False
        self.health_server = None
        self.health_server_thread = None
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("traffic_producer")
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler if specified
        if self.config.log_file:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def load_sensor_metadata(self) -> None:
        """Load sensor metadata from CSV file"""
        self.logger.info(f"Loading sensor metadata from {self.config.metadata_file}")
        
        try:
            with open(self.config.metadata_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    sensor = SensorMetadata(
                        sensor_id=row['sensor_id'],
                        latitude=float(row['latitude']),
                        longitude=float(row['longitude']),
                        road_type=row['road_type'],
                        road_name=row['road_name'],
                        direction=row['direction'],
                        lanes=int(row['lanes']),
                        installation_date=row['installation_date']
                    )
                    self.sensor_metadata[sensor.sensor_id] = sensor
            
            self.logger.info(f"Loaded metadata for {len(self.sensor_metadata)} sensors")
            
        except Exception as e:
            self.logger.error(f"Failed to load sensor metadata: {e}")
            raise
    
    def initialize_producer(self) -> None:
        """Initialize Kafka producer with configuration and connection testing"""
        self.logger.info("Initializing Kafka producer...")
        
        producer_config = {
            'bootstrap_servers': self.config.kafka_bootstrap_servers,
            'acks': self.config.acks,
            'retries': self.config.retries,
            'max_in_flight_requests_per_connection': self.config.max_in_flight,
            'linger_ms': self.config.linger_ms,
            'buffer_memory': self.config.buffer_memory,
            'compression_type': self.config.compression_type,
            'key_serializer': lambda x: x.encode('utf-8') if x else None,
            'value_serializer': lambda x: json.dumps(x).encode('utf-8'),
            # Additional producer optimizations
            'batch_size': 16384,  # 16KB batches
            'request_timeout_ms': 30000,
            'connections_max_idle_ms': 540000,
            'reconnect_backoff_ms': 50,
            'retry_backoff_ms': 100
        }
        
        try:
            self.producer = KafkaProducer(**producer_config)
            
            # Test connection by getting cluster metadata
            self._test_kafka_connection()
            
            self.logger.info("Kafka producer initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka producer: {e}")
            raise
    
    def _test_kafka_connection(self):
        """Test Kafka connection and topic existence"""
        try:
            if not self.producer:
                raise Exception("Producer not initialized")
                
            # Get cluster metadata to test connection
            metadata = self.producer.cluster
            
            self.logger.info(f"Connected to Kafka cluster with {len(metadata.brokers)} brokers")
            
            # Check if target topic exists
            if self.config.topic_name in metadata.topics:
                topic_metadata = metadata.topics[self.config.topic_name]
                self.logger.info(f"Topic '{self.config.topic_name}' found with {len(topic_metadata.partitions)} partitions")
            else:
                self.logger.warning(f"Topic '{self.config.topic_name}' not found - it will be created on first message")
                
        except Exception as e:
            self.logger.error(f"Kafka connection test failed: {e}")
            raise
    
    def start_health_server(self):
        """Start HTTP health check server"""
        try:
            # Create handler with producer reference
            handler = lambda *args, **kwargs: HealthCheckHandler(self, *args, **kwargs)
            
            # Find available port starting from configured port
            port = self.config.health_check_port
            max_attempts = 10
            
            for attempt in range(max_attempts):
                try:
                    self.health_server = HTTPServer(('localhost', port), handler)
                    break
                except OSError as e:
                    if e.errno == 10048:  # Port already in use
                        port += 1
                        if attempt == max_attempts - 1:
                            raise Exception(f"Could not find available port after {max_attempts} attempts")
                    else:
                        raise
            
            self.logger.info(f"Health check server starting on port {port}")
            
            # Start server in daemon thread
            if self.health_server:
                self.health_server_thread = threading.Thread(
                    target=self.health_server.serve_forever,
                    daemon=True
                )
                self.health_server_thread.start()
            
            self.logger.info(f"Health endpoints available at:")
            self.logger.info(f"  - Health check: http://localhost:{port}/health")
            self.logger.info(f"  - Metrics: http://localhost:{port}/metrics")
            
        except Exception as e:
            self.logger.error(f"Failed to start health server: {e}")
            # Don't fail the entire producer if health server fails
    
    def stop_health_server(self):
        """Stop HTTP health check server"""
        if self.health_server:
            self.logger.info("Stopping health check server...")
            self.health_server.shutdown()
            self.health_server.server_close()
            
            if self.health_server_thread:
                self.health_server_thread.join(timeout=5)
    
    def convert_csv_row_to_event(self, row: Dict[str, str], event_counter: int) -> TrafficEvent:
        """Convert CSV row to TrafficEvent object"""
        sensor_id = row['sensor_id']
        sensor_meta = self.sensor_metadata.get(sensor_id)
        
        if not sensor_meta:
            self.logger.warning(f"No metadata found for sensor {sensor_id}")
            # Use data from CSV as fallback
            sensor_meta = SensorMetadata(
                sensor_id=sensor_id,
                latitude=float(row['latitude']),
                longitude=float(row['longitude']),
                road_type=row['road_type'],
                road_name=row['road_name'],
                direction=row['direction'],
                lanes=3,  # Default
                installation_date="2022-01-01"  # Default
            )
        
        # Parse timestamp
        timestamp_str = row['timestamp']
        timestamp_dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        timestamp_ms = int(timestamp_dt.timestamp() * 1000)
        
        # Parse numerical values (handle empty strings)
        speed = float(row['speed_mph']) * 1.60934 if row['speed_mph'] else None  # Convert mph to km/h
        volume = int(float(row['volume_vehicles_per_hour'])) if row['volume_vehicles_per_hour'] else None
        
        # Calculate occupancy from volume (simplified estimation)
        occupancy = None
        if volume is not None and speed is not None:
            # Simple occupancy estimation: higher volume and lower speed = higher occupancy
            occupancy = min(100.0, (volume / 1000.0) * 100 + (1 - speed / 100.0) * 50)
        
        # Create segment ID from sensor and road information
        segment_id = f"SEG_{sensor_id}_{sensor_meta.road_name.replace(' ', '_')}"
        
        # Generate event ID
        event_id = f"EVT_{sensor_id}_{timestamp_ms}_{event_counter}"
        
        # Calculate quality score based on data completeness
        quality_score = 1.0
        if speed is None:
            quality_score -= 0.3
        if volume is None:
            quality_score -= 0.3
        quality_score = max(0.1, quality_score)  # Minimum quality score
        
        return TrafficEvent(
            event_id=event_id,
            segment_id=segment_id,
            timestamp=timestamp_ms,
            speed=speed,
            volume=volume,
            occupancy=occupancy,
            coordinates={
                "latitude": sensor_meta.latitude,
                "longitude": sensor_meta.longitude
            },
            source="SENSOR",
            quality_score=quality_score,
            metadata={
                "sensor_id": sensor_id,
                "road_type": sensor_meta.road_type,
                "road_name": sensor_meta.road_name,
                "direction": sensor_meta.direction,
                "lanes": str(sensor_meta.lanes),
                "original_timestamp": timestamp_str
            }
        )
    
    def delivery_callback(self, record_metadata, exception):
        """Callback for message delivery confirmation"""
        if exception is not None:
            self.logger.error(f"Message delivery failed: {exception}")
            self.metrics.record_failure()
        else:
            # Estimate message size (record_metadata doesn't provide serialized_value_size)
            estimated_size = len(str(record_metadata.topic)) + len(str(record_metadata.partition)) + 500  # Rough estimate
            self.metrics.record_success(estimated_size)
    
    def log_metrics(self):
        """Log current metrics"""
        stats = self.metrics.get_stats()
        self.logger.info(
            f"Metrics - Sent: {stats['messages_sent']}, "
            f"Failed: {stats['messages_failed']}, "
            f"Throughput: {stats['current_throughput']:.2f} msg/s, "
            f"Success Rate: {stats['success_rate']:.2%}, "
            f"Runtime: {stats['runtime_seconds']:.1f}s"
        )
    
    def start_streaming(self):
        """Start the data streaming process"""
        self.running = True
        
        # Start health check server
        self.start_health_server()
        
        # Start metrics logging thread
        metrics_thread = threading.Thread(target=self._metrics_logger_loop, daemon=True)
        metrics_thread.start()
        
        try:
            if self.config.loop_data:
                self.logger.info("Starting continuous data streaming (loop mode)")
                while self.running:
                    self._stream_csv_data()
                    if not self.running:
                        break
                    self.logger.info("Completed one loop, restarting...")
            else:
                self.logger.info("Starting single-pass data streaming")
                self._stream_csv_data()
                self.logger.info("Single-pass streaming completed")
                
        except KeyboardInterrupt:
            self.logger.info("Streaming interrupted by user")
        except Exception as e:
            self.logger.error(f"Streaming failed: {e}")
            raise
        finally:
            self.running = False
            self.stop_health_server()
    
    def _metrics_logger_loop(self):
        """Background thread for logging metrics"""
        while self.running:
            time.sleep(self.config.metrics_interval)
            if self.running:
                self.log_metrics()
    
    def _stream_csv_data(self):
        """Stream CSV data to Kafka with timing simulation"""
        self.logger.info(f"Reading data from {self.config.data_file}")
        
        batch = []
        last_timestamp = None
        event_counter = 0
        
        try:
            with open(self.config.data_file, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    if not self.running:
                        break
                        
                    try:
                        # Parse current timestamp
                        current_timestamp = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                        
                        # Handle timing simulation for realistic replay
                        if last_timestamp is not None and self.config.replay_speed > 0:
                            time_diff = (current_timestamp - last_timestamp).total_seconds()
                            sleep_time = time_diff / self.config.replay_speed
                            
                            if sleep_time > 0:
                                time.sleep(sleep_time)
                        
                        last_timestamp = current_timestamp
                        
                        # Convert CSV row to traffic event
                        traffic_event = self.convert_csv_row_to_event(row, event_counter)
                        event_counter += 1
                        
                        # Add to batch
                        batch.append(traffic_event)
                        
                        # Send batch when full
                        if len(batch) >= self.config.batch_size:
                            self._send_batch(batch)
                            batch = []
                        
                        # Update throughput metrics
                        self.metrics.update_throughput()
                        
                        # Check max records limit
                        if self.config.max_records and event_counter >= self.config.max_records:
                            self.logger.info(f"Reached max records limit: {self.config.max_records}")
                            break
                        
                        # Log progress periodically
                        if event_counter % 1000 == 0:
                            self.logger.info(f"Processed {event_counter} records")
                    
                    except Exception as e:
                        self.logger.error(f"Error processing row {event_counter}: {e}")
                        self.metrics.record_failure()
                        continue
                
                # Send remaining batch
                if batch and self.running:
                    self._send_batch(batch)
                
                self.logger.info(f"Completed streaming {event_counter} records")
                
        except Exception as e:
            self.logger.error(f"Error reading CSV file: {e}")
            raise
    
    def _send_batch(self, batch: List[TrafficEvent]):
        """Send a batch of traffic events to Kafka"""
        if not self.producer:
            self.logger.error("Kafka producer not initialized")
            return
            
        try:
            for event in batch:
                if not self.running:
                    break
                    
                # Convert TrafficEvent to dictionary for JSON serialization
                event_dict = {
                    'event_id': event.event_id,
                    'segment_id': event.segment_id,
                    'timestamp': event.timestamp,
                    'coordinates': event.coordinates,
                    'speed_kmh': event.speed,
                    'volume_vph': event.volume,
                    'occupancy_percent': event.occupancy,
                    'source': event.source,
                    'quality_score': event.quality_score,
                    'metadata': event.metadata
                }
                
                # Send message to Kafka with partition key
                future = self.producer.send(
                    self.config.topic_name,
                    value=event_dict,
                    key=event.segment_id
                )
                
                # Add delivery callback
                future.add_callback(lambda record_metadata: self.delivery_callback(record_metadata, None))
                future.add_errback(lambda exception: self.delivery_callback(None, exception))
            
            # Flush to ensure delivery
            self.producer.flush()
            
        except Exception as e:
            self.logger.error(f"Error sending batch: {e}")
            # Record failures for the entire batch
            for _ in batch:
                self.metrics.record_failure()
            raise


def load_config_from_file(config_file: str) -> ProducerConfig:
    """Load configuration from INI file"""
    config = configparser.ConfigParser()
    config.read(config_file)
    
    kwargs = {}
    if 'producer' in config:
        for key, value in config['producer'].items():
            # Convert string values to appropriate types
            if key in ['replay_speed']:
                kwargs[key] = float(value)
            elif key in ['batch_size', 'max_records', 'retries', 'max_in_flight', 'linger_ms', 'buffer_memory', 'health_check_port', 'metrics_interval']:
                kwargs[key] = int(value) if value else None
            elif key in ['loop_data']:
                kwargs[key] = value.lower() in ['true', '1', 'yes', 'on']
            else:
                kwargs[key] = value
    
    return ProducerConfig(**kwargs)


def create_default_config_file(config_file: str):
    """Create a default configuration file"""
    config = configparser.ConfigParser()
    config['producer'] = {
        'kafka_bootstrap_servers': 'localhost:9092',
        'topic_name': 'traffic-raw',
        'data_file': 'data/raw/metr_la_sample_data.csv',
        'metadata_file': 'data/raw/metr_la_sensor_metadata.csv',
        'replay_speed': '1.0',
        'batch_size': '100',
        'max_records': '',
        'loop_data': 'false',
        'compression_type': 'snappy',
        'acks': '1',
        'retries': '3',
        'max_in_flight': '5',
        'linger_ms': '100',
        'buffer_memory': '33554432',
        'log_level': 'INFO',
        'log_file': '',
        'health_check_port': '8080',
        'metrics_interval': '30'
    }
    
    with open(config_file, 'w') as f:
        config.write(f)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='METR-LA Traffic Data Producer for Kafka')
    parser.add_argument('--config', '-c', default='producer_config.ini', help='Configuration file path')
    parser.add_argument('--create-config', action='store_true', help='Create default configuration file')
    parser.add_argument('--topic', '-t', help='Kafka topic name (overrides config)')
    parser.add_argument('--speed', '-s', type=float, help='Replay speed multiplier (overrides config)')
    parser.add_argument('--max-records', '-m', type=int, help='Maximum records to send (overrides config)')
    parser.add_argument('--log-level', '-l', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Log level (overrides config)')
    
    args = parser.parse_args()
    
    # Create default config if requested
    if args.create_config:
        create_default_config_file(args.config)
        print(f"Created default configuration file: {args.config}")
        return
    
    # Load configuration
    if os.path.exists(args.config):
        config = load_config_from_file(args.config)
    else:
        print(f"Configuration file {args.config} not found. Creating default...")
        create_default_config_file(args.config)
        config = load_config_from_file(args.config)
    
    # Override config with command line arguments
    if args.topic:
        config.topic_name = args.topic
    if args.speed:
        config.replay_speed = args.speed
    if args.max_records:
        config.max_records = args.max_records
    if args.log_level:
        config.log_level = args.log_level
    
    # Initialize and run producer
    producer = TrafficDataProducer(config)
    
    try:
        producer.logger.info("Starting Traffic Data Producer...")
        producer.logger.info(f"Configuration: {asdict(config)}")
        
        # Load metadata and initialize producer
        producer.load_sensor_metadata()
        producer.initialize_producer()
        
        producer.logger.info("Producer initialized successfully. Ready to stream data...")
        producer.logger.info("Press Ctrl+C to stop gracefully")
        
        # Start data streaming
        producer.start_streaming()
            
    except KeyboardInterrupt:
        producer.logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        producer.logger.error(f"Producer failed: {e}", exc_info=True)
    finally:
        producer.running = False
        
        # Close Kafka producer
        if producer.producer:
            producer.logger.info("Closing Kafka producer...")
            producer.producer.close()
        
        # Stop health server
        producer.stop_health_server()
        
        producer.logger.info("Producer shutdown complete")


if __name__ == "__main__":
    main()