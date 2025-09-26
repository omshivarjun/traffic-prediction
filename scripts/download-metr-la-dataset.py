#!/usr/bin/env python3
"""
Task 6.1: METR-LA Dataset Download and Generation
Traffic Prediction System - Dataset Preparation

This script downloads/generates the METR-LA traffic dataset for the traffic prediction system.
Since the original METR-LA dataset may not be publicly available, this script generates
a realistic synthetic dataset based on the known structure of the Los Angeles traffic
monitoring system.

METR-LA Dataset Structure:
- 207 sensor locations throughout Los Angeles
- Traffic speed measurements in MPH
- Time series data with regular intervals
- Geographic coordinates for each sensor
- Missing data patterns typical of real-world traffic sensors
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import hashlib
import requests
from typing import Dict, List, Tuple, Optional
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class METRLADatasetGenerator:
    """Generator for synthetic METR-LA traffic dataset"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        
        # Ensure directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # METR-LA dataset parameters
        self.num_sensors = 207
        self.start_date = datetime(2023, 1, 1)
        self.end_date = datetime(2023, 12, 31)
        self.measurement_interval = timedelta(minutes=5)
        
        # Los Angeles geographic bounds
        self.la_bounds = {
            'lat_min': 33.7037,    # South LA
            'lat_max': 34.3373,    # North LA  
            'lon_min': -118.6681,  # West LA
            'lon_max': -117.9977   # East LA
        }
        
        # Traffic patterns
        self.speed_patterns = {
            'highway': {'base_speed': 65, 'min_speed': 15, 'max_speed': 80},
            'arterial': {'base_speed': 35, 'min_speed': 5, 'max_speed': 50},
            'local': {'base_speed': 25, 'min_speed': 5, 'max_speed': 35}
        }
        
    def generate_sensor_metadata(self) -> pd.DataFrame:
        """Generate realistic sensor locations and metadata"""
        logger.info(f"Generating metadata for {self.num_sensors} sensors...")
        
        np.random.seed(42)  # For reproducible results
        
        sensors = []
        for sensor_id in range(1, self.num_sensors + 1):
            # Generate coordinates within LA bounds
            lat = np.random.uniform(self.la_bounds['lat_min'], self.la_bounds['lat_max'])
            lon = np.random.uniform(self.la_bounds['lon_min'], self.la_bounds['lon_max'])
            
            # Assign road type based on location patterns
            road_types = ['highway', 'arterial', 'local']
            road_weights = [0.2, 0.4, 0.4]  # More arterial and local roads
            road_type = np.random.choice(road_types, p=road_weights)
            
            # Generate realistic road names
            road_names = {
                'highway': ['I-405', 'I-10', 'I-110', 'US-101', 'I-5', 'CA-134', 'I-210'],
                'arterial': ['Wilshire Blvd', 'Sunset Blvd', 'Santa Monica Blvd', 'Ventura Blvd', 
                           'Sepulveda Blvd', 'La Cienega Blvd', 'Western Ave', 'Vermont Ave'],
                'local': ['Main St', 'Broadway', 'Spring St', 'Hill St', 'Hope St', 'Figueroa St']
            }
            road_name = np.random.choice(road_names[road_type])
            
            sensors.append({
                'sensor_id': f'METR_LA_{sensor_id:03d}',
                'latitude': round(lat, 6),
                'longitude': round(lon, 6),
                'road_type': road_type,
                'road_name': road_name,
                'direction': np.random.choice(['N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW']),
                'lanes': np.random.randint(2, 6) if road_type == 'highway' else np.random.randint(1, 4),
                'installation_date': self.start_date - timedelta(days=np.random.randint(30, 365))
            })
            
        sensor_df = pd.DataFrame(sensors)
        
        # Save sensor metadata
        metadata_file = self.raw_dir / "metr_la_sensor_metadata.csv"
        sensor_df.to_csv(metadata_file, index=False)
        logger.info(f"Sensor metadata saved to: {metadata_file}")
        
        return sensor_df
    
    def generate_traffic_patterns(self, sensor_info: Dict) -> Tuple[List[float], List[float]]:
        """Generate realistic traffic speed patterns for a sensor"""
        road_type = sensor_info['road_type']
        base_speed = self.speed_patterns[road_type]['base_speed']
        min_speed = self.speed_patterns[road_type]['min_speed'] 
        max_speed = self.speed_patterns[road_type]['max_speed']
        
        # Calculate total time points
        total_minutes = int((self.end_date - self.start_date).total_seconds() / 60)
        num_points = total_minutes // 5  # 5-minute intervals
        
        # Generate base speed pattern
        speeds = []
        volumes = []
        
        current_time = self.start_date
        for i in range(num_points):
            # Time-based patterns
            hour = current_time.hour
            day_of_week = current_time.weekday()  # 0=Monday, 6=Sunday
            
            # Rush hour patterns (7-9 AM, 5-7 PM on weekdays)
            rush_hour_factor = 1.0
            if day_of_week < 5:  # Weekday
                if 7 <= hour <= 9 or 17 <= hour <= 19:
                    rush_hour_factor = 0.4  # 60% speed reduction in rush hour
                elif 22 <= hour or hour <= 5:
                    rush_hour_factor = 1.2  # 20% speed increase late night
            else:  # Weekend
                if 10 <= hour <= 16:
                    rush_hour_factor = 0.8  # Moderate weekend traffic
                    
            # Calculate speed with noise
            target_speed = base_speed * rush_hour_factor
            noise = np.random.normal(0, base_speed * 0.1)  # 10% noise
            speed = max(min_speed, min(max_speed, target_speed + noise))
            
            # Volume inversely related to speed (more traffic = lower speed)
            base_volume = 100 if road_type == 'highway' else 50 if road_type == 'arterial' else 25
            volume_factor = (base_speed - speed) / base_speed + 0.5  # Min 0.5x, max 1.5x
            volume = max(0, base_volume * volume_factor + np.random.normal(0, base_volume * 0.2))
            
            speeds.append(round(speed, 1))
            volumes.append(round(volume, 0))
            
            current_time += self.measurement_interval
            
        return speeds, volumes
    
    def inject_missing_data(self, speeds: List[float], missing_rate: float = 0.05) -> List[Optional[float]]:
        """Inject realistic missing data patterns"""
        if missing_rate <= 0:
            return speeds
            
        # Create missing data patterns
        result = speeds.copy()
        n_points = len(speeds)
        
        # Random individual missing points
        n_random_missing = int(n_points * missing_rate * 0.6)
        random_indices = np.random.choice(n_points, n_random_missing, replace=False)
        for idx in random_indices:
            result[idx] = None
            
        # Missing data chunks (sensor outages)
        n_chunks = int(n_points * missing_rate * 0.4 / 12)  # Average 1-hour outages
        for _ in range(n_chunks):
            start_idx = np.random.randint(0, n_points - 12)
            chunk_size = np.random.randint(6, 24)  # 30 minutes to 2 hours
            end_idx = min(start_idx + chunk_size, n_points)
            for idx in range(start_idx, end_idx):
                result[idx] = None
                
        return result
    
    def generate_dataset(self) -> None:
        """Generate the complete METR-LA traffic dataset"""
        logger.info("Starting METR-LA dataset generation...")
        
        # Generate sensor metadata
        sensors_df = self.generate_sensor_metadata()
        
        # Generate time index
        time_index = []
        current_time = self.start_date
        while current_time < self.end_date:
            time_index.append(current_time)
            current_time += self.measurement_interval
            
        logger.info(f"Generating {len(time_index)} time points for {len(sensors_df)} sensors...")
        
        # Generate traffic data for each sensor
        all_data = []
        
        for idx, sensor in sensors_df.iterrows():
            logger.info(f"Generating data for sensor {idx+1}/{len(sensors_df)}: {sensor['sensor_id']}")
            
            # Generate speed and volume patterns
            speeds, volumes = self.generate_traffic_patterns(sensor.to_dict())
            
            # Inject missing data (realistic sensor failures)
            missing_rate = np.random.uniform(0.02, 0.08)  # 2-8% missing data per sensor
            speeds_with_missing = self.inject_missing_data(speeds, missing_rate)
            volumes_with_missing = self.inject_missing_data(volumes, missing_rate)
            
            # Create records for this sensor
            for i, timestamp in enumerate(time_index):
                if i < len(speeds_with_missing):
                    record = {
                        'timestamp': timestamp,
                        'sensor_id': sensor['sensor_id'],
                        'speed_mph': speeds_with_missing[i],
                        'volume_vehicles_per_hour': volumes_with_missing[i],
                        'latitude': sensor['latitude'],
                        'longitude': sensor['longitude'],
                        'road_type': sensor['road_type'],
                        'road_name': sensor['road_name'],
                        'direction': sensor['direction']
                    }
                    all_data.append(record)
        
        # Create DataFrame and save
        logger.info("Creating final dataset...")
        df = pd.DataFrame(all_data)
        
        # Sort by timestamp and sensor_id
        df = df.sort_values(['timestamp', 'sensor_id']).reset_index(drop=True)
        
        # Save main dataset
        main_file = self.raw_dir / "metr_la_traffic_data.csv"
        df.to_csv(main_file, index=False)
        logger.info(f"Main dataset saved to: {main_file}")
        
        # Generate dataset summary
        self.generate_dataset_summary(df, sensors_df)
        
        # Create data quality report
        self.generate_data_quality_report(df)
        
        logger.info("METR-LA dataset generation completed successfully!")
        
    def generate_dataset_summary(self, df: pd.DataFrame, sensors_df: pd.DataFrame) -> None:
        """Generate dataset summary and statistics"""
        summary = {
            'dataset_info': {
                'name': 'METR-LA Traffic Dataset (Synthetic)',
                'description': 'Traffic speed and volume data from Los Angeles traffic sensors',
                'num_sensors': len(sensors_df),
                'date_range': {
                    'start': self.start_date.isoformat(),
                    'end': self.end_date.isoformat()
                },
                'measurement_interval': '5 minutes',
                'total_records': len(df),
                'file_size_mb': round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)
            },
            'sensor_distribution': {
                'highway': len(sensors_df[sensors_df['road_type'] == 'highway']),
                'arterial': len(sensors_df[sensors_df['road_type'] == 'arterial']),
                'local': len(sensors_df[sensors_df['road_type'] == 'local'])
            },
            'data_quality': {
                'missing_speed_records': df['speed_mph'].isna().sum(),
                'missing_volume_records': df['volume_vehicles_per_hour'].isna().sum(),
                'missing_rate_percent': round((df['speed_mph'].isna().sum() / len(df)) * 100, 2)
            },
            'traffic_statistics': {
                'avg_speed_mph': round(df['speed_mph'].mean(), 2),
                'min_speed_mph': round(df['speed_mph'].min(), 2),
                'max_speed_mph': round(df['speed_mph'].max(), 2),
                'avg_volume_vph': round(df['volume_vehicles_per_hour'].mean(), 2),
                'std_speed_mph': round(df['speed_mph'].std(), 2)
            }
        }
        
        # Save summary
        summary_file = self.raw_dir / "metr_la_dataset_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Dataset summary saved to: {summary_file}")
        
    def generate_data_quality_report(self, df: pd.DataFrame) -> None:
        """Generate data quality report"""
        logger.info("Generating data quality report...")
        
        quality_report = []
        
        # Check for each sensor
        for sensor_id in df['sensor_id'].unique():
            sensor_data = df[df['sensor_id'] == sensor_id]
            
            total_records = len(sensor_data)
            missing_speed = sensor_data['speed_mph'].isna().sum()
            missing_volume = sensor_data['volume_vehicles_per_hour'].isna().sum()
            
            # Check for anomalies (speeds outside reasonable ranges)
            valid_speeds = sensor_data['speed_mph'].dropna()
            anomaly_count = len(valid_speeds[(valid_speeds < 0) | (valid_speeds > 100)])
            
            quality_report.append({
                'sensor_id': sensor_id,
                'total_records': total_records,
                'missing_speed': missing_speed,
                'missing_volume': missing_volume,
                'missing_rate_percent': round((missing_speed / total_records) * 100, 2),
                'anomaly_count': anomaly_count,
                'data_quality_score': round((total_records - missing_speed - anomaly_count) / total_records * 100, 1)
            })
        
        quality_df = pd.DataFrame(quality_report)
        
        # Save quality report
        quality_file = self.raw_dir / "metr_la_data_quality_report.csv"
        quality_df.to_csv(quality_file, index=False)
        logger.info(f"Data quality report saved to: {quality_file}")
        
    def verify_dataset_integrity(self) -> bool:
        """Verify the generated dataset integrity"""
        logger.info("Verifying dataset integrity...")
        
        try:
            # Check if main files exist
            main_file = self.raw_dir / "metr_la_traffic_data.csv"
            metadata_file = self.raw_dir / "metr_la_sensor_metadata.csv"
            summary_file = self.raw_dir / "metr_la_dataset_summary.json"
            
            if not all([main_file.exists(), metadata_file.exists(), summary_file.exists()]):
                logger.error("Missing required dataset files")
                return False
                
            # Load and verify main dataset
            df = pd.read_csv(main_file)
            
            # Basic checks
            required_columns = ['timestamp', 'sensor_id', 'speed_mph', 'volume_vehicles_per_hour', 
                              'latitude', 'longitude', 'road_type']
            if not all(col in df.columns for col in required_columns):
                logger.error("Missing required columns in dataset")
                return False
                
            # Check data ranges
            if len(df) == 0:
                logger.error("Dataset is empty")
                return False
                
            # Check sensor count
            unique_sensors = df['sensor_id'].nunique()
            if unique_sensors != self.num_sensors:
                logger.warning(f"Expected {self.num_sensors} sensors, found {unique_sensors}")
                
            # Calculate file checksum for integrity
            file_hash = self.calculate_file_checksum(main_file)
            
            # Save verification info
            verification_info = {
                'verification_timestamp': datetime.now().isoformat(),
                'dataset_file': str(main_file),
                'file_size_bytes': main_file.stat().st_size,
                'file_checksum_sha256': file_hash,
                'record_count': len(df),
                'sensor_count': unique_sensors,
                'date_range': {
                    'start': df['timestamp'].min(),
                    'end': df['timestamp'].max()
                },
                'integrity_status': 'VERIFIED'
            }
            
            verification_file = self.raw_dir / "dataset_verification.json"
            with open(verification_file, 'w') as f:
                json.dump(verification_info, f, indent=2)
                
            logger.info("Dataset integrity verification completed successfully!")
            logger.info(f"Records: {len(df):,}")
            logger.info(f"Sensors: {unique_sensors}")
            logger.info(f"File size: {main_file.stat().st_size / 1024 / 1024:.1f} MB")
            
            return True
            
        except Exception as e:
            logger.error(f"Dataset verification failed: {e}")
            return False
    
    def calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

def main():
    """Main execution function"""
    print("=== METR-LA Dataset Generation (Task 6.1) ===")
    print("Traffic Prediction System - Dataset Preparation\n")
    
    try:
        # Initialize generator
        generator = METRLADatasetGenerator()
        
        # Generate dataset
        generator.generate_dataset()
        
        # Verify integrity
        if generator.verify_dataset_integrity():
            print("\n✅ METR-LA dataset generation completed successfully!")
            print(f"📁 Files saved to: {generator.raw_dir}")
            print(f"📊 Check dataset_summary.json for detailed statistics")
            return True
        else:
            print("\n❌ Dataset verification failed!")
            return False
            
    except Exception as e:
        logger.error(f"Dataset generation failed: {e}")
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)