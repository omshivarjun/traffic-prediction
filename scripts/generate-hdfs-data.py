#!/usr/bin/env python3
"""
Direct HDFS Traffic Data Generator
Generates realistic METR-LA traffic data and writes directly to HDFS
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List
import logging
import tempfile
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HDFSTrafficDataGenerator:
    def __init__(self):
        # METR-LA sensor locations (207 sensors across LA highways)
        self.sensor_locations = self._generate_sensor_network()
        
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
    
    def generate_historical_data(self, hours: int = 24) -> List[Dict]:
        """Generate historical traffic data for multiple hours"""
        events = []
        start_time = datetime.now() - timedelta(hours=hours)
        
        for hour in range(hours):
            current_time = start_time + timedelta(hours=hour)
            
            # Generate data for each sensor for this hour
            for sensor in self.sensor_locations:
                # Generate 12 events per hour (every 5 minutes)
                for minute_interval in range(0, 60, 5):
                    event_time = current_time + timedelta(minutes=minute_interval)
                    event = self._generate_traffic_event(sensor, event_time)
                    events.append(event)
        
        return events
    
    def _generate_traffic_event(self, sensor: Dict, timestamp: datetime) -> Dict:
        """Generate a single traffic event"""
        # Get time-based traffic pattern
        pattern_multiplier = self._get_traffic_pattern_multiplier(timestamp.hour)
        
        # Base traffic conditions
        base_speed = random.uniform(45, 75)
        base_volume = random.randint(800, 1500)
        
        # Apply time-based congestion
        actual_speed = max(10, base_speed * (2 - pattern_multiplier))
        actual_volume = int(base_volume * pattern_multiplier)
        
        # Calculate occupancy and congestion level
        occupancy = min(95, max(5, (actual_volume / 15) + random.uniform(-10, 10)))
        
        if actual_speed > 60:
            congestion_level = random.randint(1, 3)
        elif actual_speed > 45:
            congestion_level = random.randint(3, 5)
        elif actual_speed > 25:
            congestion_level = random.randint(5, 7)
        else:
            congestion_level = random.randint(7, 10)
        
        return {
            'event_id': str(uuid.uuid4()),
            'sensor_id': sensor['sensor_id'],
            'timestamp': timestamp.isoformat(),
            'location': {
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
                'congestion_level': congestion_level
            },
            'weather': self._generate_weather(),
            'hour': timestamp.hour,
            'day_of_week': timestamp.weekday(),
            'is_weekend': timestamp.weekday() >= 5
        }
    
    def _get_traffic_pattern_multiplier(self, hour: int) -> float:
        """Get congestion multiplier based on time of day"""
        if 6 <= hour < 10:
            return 1.8  # Morning rush
        elif 10 <= hour < 15:
            return 1.0  # Midday
        elif 15 <= hour < 19:
            return 2.0  # Evening rush
        else:
            return 0.4  # Night
    
    def _generate_weather(self) -> Dict:
        """Generate weather conditions"""
        conditions = ['clear', 'cloudy', 'light_rain', 'heavy_rain', 'fog']
        condition = random.choice(conditions)
        
        return {
            'condition': condition,
            'temperature_f': random.randint(60, 85),
            'visibility_miles': random.uniform(2.0, 10.0) if condition in ['fog', 'heavy_rain'] else 10.0,
            'precipitation': condition in ['light_rain', 'heavy_rain']
        }
    
    def write_to_hdfs(self, data: List[Dict], hdfs_path: str):
        """Write data to HDFS using docker exec"""
        logger.info(f"Writing {len(data)} events to HDFS: {hdfs_path}")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            for event in data:
                tmp_file.write(json.dumps(event) + '\n')
            tmp_filename = tmp_file.name
        
        try:
            # Copy to Docker container
            container_path = f"/tmp/{os.path.basename(tmp_filename)}"
            os.system(f"docker cp {tmp_filename} namenode:{container_path}")
            
            # Move to HDFS
            os.system(f"docker exec namenode hdfs dfs -put {container_path} {hdfs_path}")
            
            # Cleanup
            os.system(f"docker exec namenode rm {container_path}")
            
        finally:
            os.unlink(tmp_filename)
        
        logger.info(f"Successfully written data to {hdfs_path}")

if __name__ == "__main__":
    generator = HDFSTrafficDataGenerator()
    
    print("🚀 Generating Historical METR-LA Traffic Data for HDFS")
    print(f"📍 Configured {len(generator.sensor_locations)} sensors")
    
    # Generate 24 hours of historical data
    print("📊 Generating 24 hours of traffic data...")
    historical_data = generator.generate_historical_data(hours=24)
    
    print(f"✅ Generated {len(historical_data)} traffic events")
    
    # Write to HDFS in time-partitioned structure
    current_time = datetime.now()
    hdfs_path = f"/traffic-data/raw/year={current_time.year}/month={current_time.month:02d}/day={current_time.day:02d}/metr-la-historical.jsonl"
    
    generator.write_to_hdfs(historical_data, hdfs_path)
    
    print(f"🎯 Data successfully written to HDFS: {hdfs_path}")
    print("🔄 Ready for Spark processing!")