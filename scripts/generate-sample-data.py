#!/usr/bin/env python3
"""
Simple METR-LA CSV Data Generator
Generates sample traffic data for testing the pipeline
"""

import pandas as pd
import numpy as np
import argparse
import os
from datetime import datetime, timedelta

def generate_sample_data(samples=1000):
    """Generate synthetic METR-LA traffic data"""
    
    np.random.seed(42)  # For reproducible data
    
    # METR-LA sensor configuration
    sensor_ids = [f"773{i:03d}" for i in range(1, 51)]  # 50 sensors for testing
    
    data = []
    start_time = datetime(2023, 1, 1, 0, 0, 0)
    
    for i in range(samples):
        timestamp = start_time + timedelta(minutes=5 * i)
        
        # Generate data for random subset of sensors
        active_sensors = np.random.choice(sensor_ids, size=np.random.randint(5, 15), replace=False)
        
        for sensor_id in active_sensors:
            # Generate realistic speed based on time of day
            hour = timestamp.hour
            if 6 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
                speed = np.random.normal(25, 10)
            elif 22 <= hour or hour <= 5:  # Night
                speed = np.random.normal(60, 8)
            else:  # Regular hours
                speed = np.random.normal(45, 12)
            
            speed = max(5, min(80, speed))  # Clamp to realistic range
            
            record = {
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'sensor_id': sensor_id,
                'speed_mph': round(speed, 2),
                'latitude': round(34.0 + np.random.uniform(-0.3, 0.3), 6),
                'longitude': round(-118.2 + np.random.uniform(-0.3, 0.3), 6),
                'segment_id': f"seg_{sensor_id}",
                'road_type': np.random.choice(['highway', 'arterial', 'local']),
                'lane_count': np.random.randint(1, 5)
            }
            
            data.append(record)
    
    return pd.DataFrame(data)

def main():
    parser = argparse.ArgumentParser(description='Generate METR-LA sample CSV data')
    parser.add_argument('--output', '-o', default='data/processed/metr_la_sample.csv')
    parser.add_argument('--samples', '-s', type=int, default=1000)
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    print(f"Generating {args.samples} sample records...")
    df = generate_sample_data(args.samples)
    
    df.to_csv(args.output, index=False)
    
    print(f"Generated {len(df)} records")
    print(f"Data saved to: {args.output}")
    print(f"Sample records:")
    print(df.head())

if __name__ == "__main__":
    main()