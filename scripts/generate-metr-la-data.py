#!/usr/bin/env python3
"""
METR-LA Traffic Data Generator and Kafka Producer
Generates realistic traffic data for 207 LA sensors and streams to Kafka
"""

import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from kafka import KafkaProducer
import uuid
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetrLADataGenerator:
    def __init__(self):
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8')
        )
        
        # METR-LA sensor locations (207 sensors across LA highways)
        self.sensor_locations = self._generate_sensor_network()
        
        # Traffic patterns by time of day
        self.traffic_patterns = {
            'morning_rush': {'start': 6, 'end': 10, 'congestion_multiplier': 1.8},
            'midday': {'start': 10, 'end': 15, 'congestion_multiplier': 1.0},
            'evening_rush': {'start': 15, 'end': 19, 'congestion_multiplier': 2.0},
            'night': {'start': 19, 'end': 6, 'congestion_multiplier': 0.4}
        }
        
    def _generate_sensor_network(self) -> List[Dict]:
        """Generate 207 sensor locations across LA highways"""
        highways = {
            'I-405': {'lat_center': 34.0522, 'lon_center': -118.2437, 'sensors': 52},
            'US-101': {'lat_center': 34.0928, 'lon_center': -118.3287, 'sensors': 45},
            'I-10': {'lat_center': 34.0194, 'lon_center': -118.4912, 'sensors': 38},
            'I-210': {'lat_center': 34.2140, 'lon_center': -118.1719, 'sensors': 32},
            'I-110': {'lat_center': 34.0261, 'lon_center': -118.2661, 'sensors': 25},
            'I-5': {'lat_center': 34.1139, 'lon_center': -118.4068, 'sensors': 15}
        }
        
        sensors = []
        sensor_id = 1
        
        for highway, config in highways.items():
            for i in range(config['sensors']):
                # Distribute sensors along highway with some randomness
                lat_offset = random.uniform(-0.05, 0.05)
                lon_offset = random.uniform(-0.08, 0.08)
                
                sensor = {
                    'sensor_id': f'LA_{sensor_id:03d}',
                    'highway': highway,
                    'latitude': config['lat_center'] + lat_offset,
                    'longitude': config['lon_center'] + lon_offset,
                    'mile_marker': round(random.uniform(1.0, 50.0), 1),
                    'direction': random.choice(['N', 'S', 'E', 'W']),
                    'lanes': random.randint(2, 5)
                }
                sensors.append(sensor)
                sensor_id += 1
                
        return sensors
    
    def _get_traffic_pattern_multiplier(self, current_hour: int) -> float:
        """Get congestion multiplier based on time of day"""
        if 6 <= current_hour < 10:
            return self.traffic_patterns['morning_rush']['congestion_multiplier']
        elif 10 <= current_hour < 15:
            return self.traffic_patterns['midday']['congestion_multiplier']
        elif 15 <= current_hour < 19:
            return self.traffic_patterns['evening_rush']['congestion_multiplier']
        else:
            return self.traffic_patterns['night']['congestion_multiplier']
    
    def generate_traffic_event(self, sensor: Dict, timestamp: datetime) -> Dict:
        """Generate a single traffic event for a sensor"""
        
        # Get time-based traffic pattern
        pattern_multiplier = self._get_traffic_pattern_multiplier(timestamp.hour)
        
        # Generate realistic speed distribution across all congestion levels
        # Pattern multiplier: night=0.4, midday=1.0, morning=1.8, evening=2.0
        
        # Random factor for variety (some sensors always have good/bad traffic)
        sensor_variance = random.uniform(0.7, 1.3)
        
        if pattern_multiplier < 0.6:  # Night time - mostly free flow
            speed_distribution = random.choices(
                [random.uniform(70, 85), random.uniform(60, 75), random.uniform(45, 65), random.uniform(25, 45), random.uniform(10, 25)],
                weights=[50, 30, 15, 4, 1]  # 50% free flow, 30% light, 15% moderate, 4% heavy, 1% severe
            )[0]
        elif pattern_multiplier < 1.2:  # Midday - mixed
            speed_distribution = random.choices(
                [random.uniform(70, 85), random.uniform(60, 75), random.uniform(45, 65), random.uniform(25, 45), random.uniform(10, 25)],
                weights=[30, 35, 25, 8, 2]  # 30% free flow, 35% light, 25% moderate, 8% heavy, 2% severe
            )[0]
        elif pattern_multiplier < 1.9:  # Morning rush - more congestion
            speed_distribution = random.choices(
                [random.uniform(70, 85), random.uniform(60, 75), random.uniform(45, 65), random.uniform(25, 45), random.uniform(10, 25)],
                weights=[15, 25, 35, 20, 5]  # 15% free flow, 25% light, 35% moderate, 20% heavy, 5% severe
            )[0]
        else:  # Evening rush - most congestion
            speed_distribution = random.choices(
                [random.uniform(70, 85), random.uniform(60, 75), random.uniform(45, 65), random.uniform(25, 45), random.uniform(10, 25)],
                weights=[10, 20, 30, 30, 10]  # 10% free flow, 20% light, 30% moderate, 30% heavy, 10% severe
            )[0]
        
        actual_speed = round(speed_distribution * sensor_variance, 1)
        actual_speed = max(5, min(90, actual_speed))  # Clamp between 5-90 mph
        
        # Volume increases during congestion
        base_volume = random.randint(800, 1500)
        actual_volume = int(base_volume * pattern_multiplier * random.uniform(0.8, 1.2))
        
        # Calculate occupancy based on volume and speed
        occupancy = min(95, max(5, (actual_volume / 15) + (100 - actual_speed) / 2 + random.uniform(-10, 10)))
        
        # Congestion level (1-10 scale)
        if actual_speed > 60:
            congestion_level = random.randint(1, 3)
        elif actual_speed > 45:
            congestion_level = random.randint(3, 5)
        elif actual_speed > 25:
            congestion_level = random.randint(5, 7)
        else:
            congestion_level = random.randint(7, 10)
        
        # Generate weather data
        weather_conditions = self._generate_weather()
        
        return {
            'event_id': str(uuid.uuid4()),
            'sensor_id': sensor['sensor_id'],
            'timestamp': timestamp.isoformat(),
            'location': {
                'segment_id': sensor['sensor_id'],  # Add segment_id to location for stream processor
                'sensor_id': sensor['sensor_id'],    # Add sensor_id to location
                'highway': sensor['highway'],
                'mile_marker': sensor['mile_marker'],
                'latitude': sensor['latitude'],
                'longitude': sensor['longitude'],
                'direction': sensor['direction'],
                'lanes': sensor['lanes']
            },
            'traffic_data': {
                'speed_mph': round(actual_speed, 1),
                'volume_vehicles_per_hour': actual_volume,
                'occupancy_percentage': round(occupancy, 1),
                'congestion_level': congestion_level,
                'lane_1_speed': round(actual_speed + random.uniform(-5, 5), 1),
                'lane_2_speed': round(actual_speed + random.uniform(-3, 3), 1),
                'travel_time_minutes': round((sensor['mile_marker'] / actual_speed) * 60, 1)
            },
            'weather': weather_conditions,
            'metadata': {
                'data_quality': random.choice(['excellent', 'good', 'fair']),
                'sensor_status': 'active',
                'last_calibration': (timestamp - timedelta(days=random.randint(1, 30))).isoformat()
            }
        }
    
    def _generate_weather(self) -> Dict:
        """Generate weather conditions affecting traffic"""
        conditions = ['clear', 'cloudy', 'light_rain', 'heavy_rain', 'fog']
        condition = random.choice(conditions)
        
        weather = {
            'condition': condition,
            'temperature_f': random.randint(60, 85),
            'humidity_percentage': random.randint(30, 90),
            'visibility_miles': 10.0,
            'precipitation': False
        }
        
        # Adjust visibility and precipitation based on conditions
        if condition == 'fog':
            weather['visibility_miles'] = random.uniform(0.5, 3.0)
        elif condition in ['light_rain', 'heavy_rain']:
            weather['precipitation'] = True
            weather['visibility_miles'] = random.uniform(2.0, 8.0)
            
        return weather
    
    def generate_incident(self, sensor: Dict, timestamp: datetime) -> Dict:
        """Generate traffic incident data"""
        incident_types = ['accident', 'construction', 'disabled_vehicle', 'debris', 'weather_related']
        
        return {
            'incident_id': str(uuid.uuid4()),
            'sensor_id': sensor['sensor_id'],
            'timestamp': timestamp.isoformat(),
            'incident_type': random.choice(incident_types),
            'severity': random.randint(1, 5),
            'lanes_affected': random.randint(1, min(3, sensor['lanes'])),
            'estimated_duration_minutes': random.randint(15, 180),
            'location': {
                'highway': sensor['highway'],
                'mile_marker': sensor['mile_marker'],
                'latitude': sensor['latitude'],
                'longitude': sensor['longitude']
            },
            'description': f"Traffic incident on {sensor['highway']} at mile {sensor['mile_marker']}"
        }
    
    def stream_data_to_kafka(self, duration_minutes: Optional[int] = None, interval_seconds: int = 5):
        """Stream generated traffic data to Kafka topics (continuously if duration_minutes is None)"""
        
        if duration_minutes:
            logger.info(f"Starting data stream for {duration_minutes} minutes...")
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=duration_minutes)
            logger.info(f"Start time: {start_time}, End time: {end_time}")
        else:
            logger.info("Starting CONTINUOUS data stream (no time limit)...")
            logger.info("Press Ctrl+C to stop")
            end_time = None
        
        logger.info(f"Generating data for {len(self.sensor_locations)} sensors")
        
        event_count = 0
        incident_count = 0
        batch_count = 0
        
        try:
            while True:
                batch_count += 1
                current_time = datetime.now()
                
                # Log batch info
                if end_time:
                    time_remaining = (end_time - current_time).total_seconds()
                    logger.info(f"[Batch {batch_count}] Time remaining: {time_remaining:.1f} seconds")
                else:
                    logger.info(f"[Batch {batch_count}] Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Generate traffic events for all sensors
                for sensor in self.sensor_locations:
                    # Traffic event (always generated)
                    traffic_event = self.generate_traffic_event(sensor, current_time)
                    
                    # Send to Kafka traffic-raw topic for stream processing
                    self.kafka_producer.send(
                        'traffic-raw',
                        key=sensor['sensor_id'],
                        value=traffic_event
                    )
                    event_count += 1
                    
                    # Generate incidents occasionally (5% chance)
                    if random.random() < 0.05:
                        incident = self.generate_incident(sensor, current_time)
                        self.kafka_producer.send(
                            'traffic-incidents',
                            key=sensor['sensor_id'],
                            value=incident
                        )
                        incident_count += 1
                
                # Flush producer
                self.kafka_producer.flush()
                
                logger.info(f"[Batch {batch_count} Complete] Total events: {event_count}, Total incidents: {incident_count}")
                
                # Check if we should stop (only if duration was specified)
                if end_time and datetime.now() >= end_time:
                    logger.info("Duration reached, exiting loop")
                    break
                
                # Wait for next interval
                logger.info(f"Sleeping for {interval_seconds} seconds...")
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("Stopping data generation...")
        
        finally:
            logger.info(f"Generated {event_count} traffic events and {incident_count} incidents")
            self.kafka_producer.close()

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate METR-LA traffic data and stream to Kafka')
    parser.add_argument('--duration', type=int, default=None, help='Duration in minutes (default: continuous/infinite)')
    parser.add_argument('--interval', type=int, default=5, help='Interval between batches in seconds (default: 5)')
    args = parser.parse_args()
    
    generator = MetrLADataGenerator()
    
    print("Starting METR-LA Traffic Data Generation")
    print(f"Configured {len(generator.sensor_locations)} sensors across LA highways")
    print("Streaming data to Kafka topics: traffic-raw, traffic-incidents")
    
    if args.duration:
        print(f"Duration: {args.duration} minutes, Interval: {args.interval} seconds")
    else:
        print(f"Mode: CONTINUOUS (no time limit), Interval: {args.interval} seconds")
    
    print("Press Ctrl+C to stop\n")
    
    # Stream data with specified duration and interval
    generator.stream_data_to_kafka(duration_minutes=args.duration, interval_seconds=args.interval)