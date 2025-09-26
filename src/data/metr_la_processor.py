"""
METR-LA Dataset Processor for Real-Time Traffic Congestion Prediction

This module handles the processing and streaming of METR-LA traffic data
for the Kafka + Hadoop pipeline.

METR-LA Dataset: Los Angeles County highway traffic data
- 207 sensors across 4 months
- Traffic flow, speed, and occupancy measurements
- 5-minute intervals
"""

import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from kafka import KafkaProducer
import pickle
import requests
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetrLAProcessor:
    """Process and stream METR-LA traffic data for congestion prediction."""
    
    def __init__(self, data_path: str = "data/raw/metr-la"):
        self.data_path = Path(data_path)
        self.sensors_df = None
        self.traffic_data = None
        self.distance_matrix = None
        
        # Kafka configuration
        self.kafka_config = {
            'bootstrap_servers': ['localhost:9093'],
            'value_serializer': lambda x: json.dumps(x).encode('utf-8'),
            'key_serializer': lambda x: x.encode('utf-8') if x else None
        }
        
        # Create data directory if it doesn't exist
        self.data_path.mkdir(parents=True, exist_ok=True)
        
    def download_metr_la_data(self) -> bool:
        """Download METR-LA dataset if not already present."""
        urls = {
            'adj_mx.pkl': 'https://github.com/liyaguang/DCRNN/raw/master/data/sensor_graph/adj_mx.pkl',
            'graph_sensor_ids.txt': 'https://github.com/liyaguang/DCRNN/raw/master/data/sensor_graph/graph_sensor_ids.txt',
            'metr-la.h5': 'https://github.com/liyaguang/DCRNN/raw/master/data/metr-la.h5'
        }
        
        try:
            for filename, url in urls.items():
                file_path = self.data_path / filename
                if not file_path.exists():
                    logger.info(f"Downloading {filename}...")
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"Downloaded {filename}")
                else:
                    logger.info(f"{filename} already exists")
            
            return True
        except Exception as e:
            logger.error(f"Error downloading METR-LA data: {e}")
            return False
    
    def load_metr_la_data(self) -> bool:
        """Load METR-LA dataset into memory."""
        try:
            # Download data if needed
            if not self.download_metr_la_data():
                return False
            
            # Load sensor IDs
            sensor_ids_path = self.data_path / 'graph_sensor_ids.txt'
            with open(sensor_ids_path, 'r') as f:
                sensor_ids = [int(line.strip()) for line in f.readlines()]
            
            # Load adjacency matrix (distance matrix)
            adj_mx_path = self.data_path / 'adj_mx.pkl'
            with open(adj_mx_path, 'rb') as f:
                self.distance_matrix = pickle.load(f)
            
            # Load traffic data
            h5_path = self.data_path / 'metr-la.h5'
            df = pd.read_hdf(h5_path)
            
            # Process the data
            self.traffic_data = df
            self.sensors_df = pd.DataFrame({
                'sensor_id': sensor_ids,
                'index': range(len(sensor_ids))
            })
            
            logger.info(f"Loaded METR-LA data: {len(sensor_ids)} sensors, {len(df)} records")
            return True
            
        except Exception as e:
            logger.error(f"Error loading METR-LA data: {e}")
            return False
    
    def calculate_congestion_level(self, speed: float, flow: float) -> str:
        """Calculate congestion level based on speed and flow."""
        if speed < 25:  # mph
            if flow > 1500:
                return "severe"
            else:
                return "heavy"
        elif speed < 45:
            if flow > 1200:
                return "moderate"
            else:
                return "light"
        else:
            return "free_flow"
    
    def process_traffic_record(self, timestamp: pd.Timestamp, sensor_idx: int, speed: float) -> Dict:
        """Process a single traffic record into structured format."""
        sensor_id = self.sensors_df.iloc[sensor_idx]['sensor_id']
        
        # Simulate additional metrics based on speed (in real implementation, these would come from data)
        flow = max(0, np.random.normal(1000, 200) * (100 - speed) / 100)  # Inverse relation with speed
        occupancy = min(100, max(0, np.random.normal(30, 10) * (100 - speed) / 100))
        
        # Calculate congestion
        congestion_level = self.calculate_congestion_level(speed, flow)
        
        # Create LA coordinates (approximate sensor locations)
        lat_base, lng_base = 34.0522, -118.2437  # LA center
        lat_offset = np.random.uniform(-0.5, 0.5)
        lng_offset = np.random.uniform(-0.5, 0.5)
        
        return {
            "event_id": f"metr_la_{sensor_id}_{int(timestamp.timestamp())}",
            "timestamp": timestamp.isoformat(),
            "sensor_id": str(sensor_id),
            "location": {
                "latitude": lat_base + lat_offset,
                "longitude": lng_base + lng_offset,
                "road_segment": f"LA_Highway_Sensor_{sensor_id}",
                "city": "Los Angeles",
                "state": "CA"
            },
            "traffic_metrics": {
                "speed_mph": round(speed, 2),
                "volume_vph": round(flow, 0),  # vehicles per hour
                "occupancy_percent": round(occupancy, 2),
                "congestion_level": congestion_level
            },
            "metadata": {
                "data_source": "METR-LA",
                "sensor_index": sensor_idx,
                "processing_timestamp": datetime.now().isoformat()
            }
        }
    
    def stream_historical_data(self, start_idx: int = 0, max_records: int = 1000, 
                             delay_ms: int = 100) -> None:
        """Stream historical METR-LA data to Kafka as if it were real-time."""
        if self.traffic_data is None:
            logger.error("No traffic data loaded. Call load_metr_la_data() first.")
            return
        
        try:
            producer = KafkaProducer(**self.kafka_config)
            
            records_sent = 0
            total_records = min(len(self.traffic_data), start_idx + max_records)
            
            logger.info(f"Starting to stream {max_records} records from index {start_idx}")
            
            for idx in range(start_idx, total_records):
                if records_sent >= max_records:
                    break
                
                # Get timestamp and all sensor readings for this time
                timestamp = self.traffic_data.index[idx]
                sensor_readings = self.traffic_data.iloc[idx]
                
                # Process each sensor reading
                for sensor_idx, speed in enumerate(sensor_readings):
                    if pd.notna(speed) and speed > 0:  # Skip invalid readings
                        try:
                            traffic_record = self.process_traffic_record(timestamp, sensor_idx, speed)
                            
                            # Send to Kafka
                            producer.send(
                                'traffic-events',
                                value=traffic_record,
                                key=traffic_record['sensor_id']
                            )
                            
                            records_sent += 1
                            
                            if records_sent % 100 == 0:
                                logger.info(f"Streamed {records_sent} traffic events...")
                                
                        except Exception as e:
                            logger.warning(f"Error processing sensor {sensor_idx}: {e}")
                            continue
                
                # Small delay to simulate real-time streaming
                if delay_ms > 0:
                    import time
                    time.sleep(delay_ms / 1000.0)
            
            producer.flush()
            producer.close()
            
            logger.info(f"Completed streaming {records_sent} traffic events from METR-LA dataset")
            
        except Exception as e:
            logger.error(f"Error streaming data: {e}")
    
    def generate_congestion_hotspots(self, num_hotspots: int = 10) -> List[Dict]:
        """Generate current congestion hotspots for the dashboard."""
        if self.traffic_data is None or self.sensors_df is None:
            return []
        
        try:
            # Get latest data (simulate current conditions)
            latest_data = self.traffic_data.iloc[-1]
            
             # Find sensors with lowest speeds (highest congestion)
            congested_sensors = latest_data.nsmallest(num_hotspots)
            
            hotspots = []
            for sensor_idx, speed in congested_sensors.items():
                if pd.notna(speed):
                    sensor_id = self.sensors_df.iloc[sensor_idx]['sensor_id']
                    
                    # Simulate LA highway names
                    highway_names = ["I-405", "US-101", "I-10", "I-110", "I-210", "SR-91", "I-605", "SR-134"]
                    highway = np.random.choice(highway_names)
                    
                    congestion_level = self.calculate_congestion_level(speed, 1000)
                    
                    hotspots.append({
                        "sensor_id": str(sensor_id),
                        "location_name": f"{highway} near Sensor {sensor_id}",
                        "current_speed": round(speed, 1),
                        "congestion_level": congestion_level,
                        "severity_score": round((100 - speed) / 100, 2),
                        "coordinates": {
                            "latitude": 34.0522 + np.random.uniform(-0.3, 0.3),
                            "longitude": -118.2437 + np.random.uniform(-0.3, 0.3)
                        }
                    })
            
            return sorted(hotspots, key=lambda x: x['severity_score'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error generating hotspots: {e}")
            return []
    
    def get_traffic_statistics(self) -> Dict:
        """Get overall traffic statistics from the dataset."""
        if self.traffic_data is None:
            return {}
        
        try:
            latest_data = self.traffic_data.iloc[-1].dropna()
            
            return {
                "active_sensors": len(latest_data),
                "average_speed": round(latest_data.mean(), 1),
                "congested_sensors": len(latest_data[latest_data < 30]),
                "free_flow_sensors": len(latest_data[latest_data > 60]),
                "total_data_points": len(self.traffic_data),
                "time_range": {
                    "start": self.traffic_data.index[0].isoformat(),
                    "end": self.traffic_data.index[-1].isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {}

# Example usage
if __name__ == "__main__":
    processor = MetrLAProcessor()
    
    # Load the dataset
    if processor.load_metr_la_data():
        logger.info("METR-LA data loaded successfully")
        
        # Print statistics
        stats = processor.get_traffic_statistics()
        logger.info(f"Dataset statistics: {stats}")
        
        # Generate hotspots
        hotspots = processor.generate_congestion_hotspots()
        logger.info(f"Current congestion hotspots: {len(hotspots)}")
        
        # Stream some sample data (uncomment to test)
        # processor.stream_historical_data(start_idx=0, max_records=500, delay_ms=50)
    else:
        logger.error("Failed to load METR-LA data")