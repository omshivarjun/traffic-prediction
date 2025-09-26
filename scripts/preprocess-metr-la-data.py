#!/usr/bin/env python3
"""
Task 6.3: Data Preprocessing Script
Traffic Prediction System - METR-LA Dataset Preprocessing

This script cleans and preprocesses the raw METR-LA traffic dataset:
- Handle missing values using forward fill and interpolation
- Remove invalid readings (negative speeds, extreme outliers)
- Normalize speed values for ML training
- Generate temporal features (hour, day_of_week, is_weekend)
- Create road type encodings
- Generate clean dataset ready for HDFS upload and ML training

The preprocessing follows traffic engineering best practices and prepares
data for the traffic prediction pipeline.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class METRLAPreprocessor:
    """Preprocessor for METR-LA traffic dataset"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        
        # Ensure processed directory exists
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Preprocessing parameters
        self.speed_bounds = {
            'highway': {'min': 10, 'max': 85, 'outlier_threshold': 3},
            'arterial': {'min': 5, 'max': 60, 'outlier_threshold': 3},
            'local': {'min': 3, 'max': 45, 'outlier_threshold': 2.5}
        }
        
        self.volume_bounds = {
            'highway': {'min': 0, 'max': 3000, 'outlier_threshold': 3},
            'arterial': {'min': 0, 'max': 1500, 'outlier_threshold': 3},
            'local': {'min': 0, 'max': 800, 'outlier_threshold': 2.5}
        }
        
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load raw traffic data and sensor metadata"""
        logger.info("Loading raw METR-LA dataset...")
        
        # Load sensor metadata
        metadata_file = self.raw_dir / "metr_la_sensor_metadata.csv"
        if not metadata_file.exists():
            raise FileNotFoundError(f"Sensor metadata not found: {metadata_file}")
        
        sensors_df = pd.read_csv(metadata_file)
        logger.info(f"Loaded {len(sensors_df)} sensor metadata records")
        
        # Load traffic data (prefer full dataset, fallback to sample)
        traffic_files = [
            self.raw_dir / "metr_la_traffic_data.csv",
            self.raw_dir / "metr_la_sample_data.csv"
        ]
        
        traffic_df = None
        for file in traffic_files:
            if file.exists():
                logger.info(f"Loading traffic data from: {file}")
                traffic_df = pd.read_csv(file)
                break
        
        if traffic_df is None:
            raise FileNotFoundError("No traffic data found")
        
        logger.info(f"Loaded {len(traffic_df):,} traffic records")
        return traffic_df, sensors_df
    
    def clean_temporal_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and enhance temporal features"""
        logger.info("Processing temporal features...")
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Sort by timestamp and sensor for proper ordering
        df = df.sort_values(['sensor_id', 'timestamp']).reset_index(drop=True)
        
        # Extract temporal features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek  # 0=Monday, 6=Sunday
        df['day_name'] = df['timestamp'].dt.day_name()
        df['is_weekend'] = df['timestamp'].dt.dayofweek >= 5
        df['month'] = df['timestamp'].dt.month
        df['quarter'] = df['timestamp'].dt.quarter
        
        # Create time-based categories
        df['time_period'] = 'other'
        df.loc[df['hour'].between(6, 9), 'time_period'] = 'morning_rush'
        df.loc[df['hour'].between(17, 19), 'time_period'] = 'evening_rush'
        df.loc[df['hour'].between(22, 6), 'time_period'] = 'late_night'
        df.loc[df['hour'].between(10, 16), 'time_period'] = 'midday'
        
        # Create rush hour flag
        df['is_rush_hour'] = df['time_period'].isin(['morning_rush', 'evening_rush'])
        
        logger.info("✅ Temporal features processed")
        return df
    
    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values using forward fill and interpolation"""
        logger.info("Handling missing values...")
        
        initial_missing = df[['speed_mph', 'volume_vehicles_per_hour']].isna().sum().sum()
        logger.info(f"Initial missing values: {initial_missing:,}")
        
        # Process each sensor separately to maintain temporal continuity
        processed_chunks = []
        
        for sensor_id in df['sensor_id'].unique():
            sensor_data = df[df['sensor_id'] == sensor_id].copy()
            sensor_data = sensor_data.sort_values('timestamp')
            
            # Forward fill missing values (carries last known value forward)
            sensor_data['speed_mph'] = sensor_data['speed_mph'].fillna(method='ffill')
            sensor_data['volume_vehicles_per_hour'] = sensor_data['volume_vehicles_per_hour'].fillna(method='ffill')
            
            # Backward fill for any remaining missing values at the beginning
            sensor_data['speed_mph'] = sensor_data['speed_mph'].fillna(method='bfill')
            sensor_data['volume_vehicles_per_hour'] = sensor_data['volume_vehicles_per_hour'].fillna(method='bfill')
            
            # Linear interpolation for remaining gaps
            sensor_data['speed_mph'] = sensor_data['speed_mph'].interpolate(method='linear')
            sensor_data['volume_vehicles_per_hour'] = sensor_data['volume_vehicles_per_hour'].interpolate(method='linear')
            
            processed_chunks.append(sensor_data)
        
        df_cleaned = pd.concat(processed_chunks, ignore_index=True)
        df_cleaned = df_cleaned.sort_values(['timestamp', 'sensor_id']).reset_index(drop=True)
        
        final_missing = df_cleaned[['speed_mph', 'volume_vehicles_per_hour']].isna().sum().sum()
        logger.info(f"Final missing values: {final_missing:,} (removed {initial_missing - final_missing:,})")
        
        return df_cleaned
    
    def remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove outliers and invalid readings"""
        logger.info("Removing outliers and invalid readings...")
        
        initial_count = len(df)
        records_removed = 0
        
        # Process by road type for appropriate bounds
        cleaned_chunks = []
        
        for road_type in df['road_type'].unique():
            if road_type not in self.speed_bounds:
                logger.warning(f"Unknown road type: {road_type}, using arterial bounds")
                road_type_key = 'arterial'
            else:
                road_type_key = road_type
                
            road_data = df[df['road_type'] == road_type].copy()
            initial_road_count = len(road_data)
            
            # Speed bounds
            speed_min = self.speed_bounds[road_type_key]['min']
            speed_max = self.speed_bounds[road_type_key]['max']
            
            # Remove clearly invalid speeds
            road_data = road_data[
                (road_data['speed_mph'] >= speed_min) & 
                (road_data['speed_mph'] <= speed_max)
            ]
            
            # Volume bounds
            volume_max = self.volume_bounds[road_type_key]['max']
            road_data = road_data[
                (road_data['volume_vehicles_per_hour'] >= 0) & 
                (road_data['volume_vehicles_per_hour'] <= volume_max)
            ]
            
            # Statistical outlier removal using IQR method
            speed_q1 = road_data['speed_mph'].quantile(0.25)
            speed_q3 = road_data['speed_mph'].quantile(0.75)
            speed_iqr = speed_q3 - speed_q1
            speed_threshold = self.speed_bounds[road_type_key]['outlier_threshold']
            
            speed_lower = speed_q1 - speed_threshold * speed_iqr
            speed_upper = speed_q3 + speed_threshold * speed_iqr
            
            # Apply outlier filtering (but respect physical bounds)
            speed_lower = max(speed_lower, speed_min)
            speed_upper = min(speed_upper, speed_max)
            
            road_data = road_data[
                (road_data['speed_mph'] >= speed_lower) & 
                (road_data['speed_mph'] <= speed_upper)
            ]
            
            # Same for volume
            volume_q1 = road_data['volume_vehicles_per_hour'].quantile(0.25)
            volume_q3 = road_data['volume_vehicles_per_hour'].quantile(0.75)
            volume_iqr = volume_q3 - volume_q1
            volume_threshold = self.volume_bounds[road_type_key]['outlier_threshold']
            
            volume_upper = volume_q3 + volume_threshold * volume_iqr
            volume_upper = min(volume_upper, volume_max)
            
            road_data = road_data[road_data['volume_vehicles_per_hour'] <= volume_upper]
            
            final_road_count = len(road_data)
            road_removed = initial_road_count - final_road_count
            records_removed += road_removed
            
            logger.info(f"  {road_type}: removed {road_removed:,} outliers ({road_removed/initial_road_count*100:.1f}%)")
            cleaned_chunks.append(road_data)
        
        df_cleaned = pd.concat(cleaned_chunks, ignore_index=True)
        df_cleaned = df_cleaned.sort_values(['timestamp', 'sensor_id']).reset_index(drop=True)
        
        logger.info(f"✅ Outlier removal complete: {records_removed:,} records removed ({records_removed/initial_count*100:.2f}%)")
        return df_cleaned
    
    def create_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create derived features for ML training"""
        logger.info("Creating derived features...")
        
        # Speed-based features
        df['speed_normalized'] = 0.0
        
        # Normalize speed by road type (0-1 scale)
        for road_type in df['road_type'].unique():
            road_mask = df['road_type'] == road_type
            if road_type in self.speed_bounds:
                speed_min = self.speed_bounds[road_type]['min']
                speed_max = self.speed_bounds[road_type]['max']
            else:
                speed_min = df[road_mask]['speed_mph'].min()
                speed_max = df[road_mask]['speed_mph'].max()
            
            df.loc[road_mask, 'speed_normalized'] = (
                (df.loc[road_mask, 'speed_mph'] - speed_min) / (speed_max - speed_min)
            )
        
        # Volume-based features
        df['volume_normalized'] = 0.0
        
        for road_type in df['road_type'].unique():
            road_mask = df['road_type'] == road_type
            if road_type in self.volume_bounds:
                volume_max = self.volume_bounds[road_type]['max']
            else:
                volume_max = df[road_mask]['volume_vehicles_per_hour'].max()
            
            df.loc[road_mask, 'volume_normalized'] = (
                df.loc[road_mask, 'volume_vehicles_per_hour'] / volume_max
            )
        
        # Traffic density (vehicles per lane per hour)
        # Use sensor metadata to get lane information
        sensor_lanes = {}
        if 'lanes' in df.columns:
            for _, row in df[['sensor_id', 'lanes']].drop_duplicates().iterrows():
                sensor_lanes[row['sensor_id']] = row['lanes']
        else:
            # Default lane assumptions by road type
            default_lanes = {'highway': 4, 'arterial': 2, 'local': 1}
            for _, row in df[['sensor_id', 'road_type']].drop_duplicates().iterrows():
                sensor_lanes[row['sensor_id']] = default_lanes.get(row['road_type'], 2)
        
        df['lanes'] = df['sensor_id'].map(sensor_lanes)
        df['traffic_density'] = df['volume_vehicles_per_hour'] / df['lanes']
        
        # Congestion indicators
        df['congestion_level'] = 'free_flow'
        
        # Define congestion thresholds by road type
        for road_type in df['road_type'].unique():
            road_mask = df['road_type'] == road_type
            road_data = df[road_mask]
            
            # Use speed percentiles to define congestion
            speed_25 = road_data['speed_mph'].quantile(0.25)
            speed_50 = road_data['speed_mph'].quantile(0.50)
            
            df.loc[road_mask & (df['speed_mph'] <= speed_25), 'congestion_level'] = 'heavy'
            df.loc[road_mask & (df['speed_mph'] <= speed_50) & (df['speed_mph'] > speed_25), 'congestion_level'] = 'moderate'
            df.loc[road_mask & (df['speed_mph'] > speed_50), 'congestion_level'] = 'free_flow'
        
        # Encode categorical variables
        df['road_type_encoded'] = df['road_type'].astype('category').cat.codes
        df['time_period_encoded'] = df['time_period'].astype('category').cat.codes
        df['congestion_level_encoded'] = df['congestion_level'].astype('category').cat.codes
        
        # Moving averages (for temporal patterns)
        logger.info("Computing temporal moving averages...")
        df = df.sort_values(['sensor_id', 'timestamp']).reset_index(drop=True)
        
        # Calculate rolling statistics per sensor
        temporal_features = []
        for sensor_id in df['sensor_id'].unique():
            sensor_data = df[df['sensor_id'] == sensor_id].copy()
            
            # 1-hour moving average (12 periods of 5 minutes)
            sensor_data['speed_1h_avg'] = sensor_data['speed_mph'].rolling(window=12, min_periods=1).mean()
            sensor_data['volume_1h_avg'] = sensor_data['volume_vehicles_per_hour'].rolling(window=12, min_periods=1).mean()
            
            # 3-hour moving average
            sensor_data['speed_3h_avg'] = sensor_data['speed_mph'].rolling(window=36, min_periods=1).mean()
            sensor_data['volume_3h_avg'] = sensor_data['volume_vehicles_per_hour'].rolling(window=36, min_periods=1).mean()
            
            temporal_features.append(sensor_data)
        
        df = pd.concat(temporal_features, ignore_index=True)
        df = df.sort_values(['timestamp', 'sensor_id']).reset_index(drop=True)
        
        logger.info("✅ Derived features created")
        return df
    
    def validate_processed_data(self, df: pd.DataFrame) -> Dict:
        """Validate the processed dataset"""
        logger.info("Validating processed dataset...")
        
        validation_results = {
            'total_records': len(df),
            'unique_sensors': df['sensor_id'].nunique(),
            'date_range': {
                'start': df['timestamp'].min().isoformat(),
                'end': df['timestamp'].max().isoformat(),
                'duration_days': (df['timestamp'].max() - df['timestamp'].min()).days
            },
            'missing_values': {
                'speed_mph': int(df['speed_mph'].isna().sum()),
                'volume_vehicles_per_hour': int(df['volume_vehicles_per_hour'].isna().sum()),
                'derived_features': int(df['speed_normalized'].isna().sum() + df['volume_normalized'].isna().sum() + df['traffic_density'].isna().sum())
            },
            'data_quality': {
                'valid_speeds': int((df['speed_mph'] > 0).sum()),
                'valid_volumes': int((df['volume_vehicles_per_hour'] >= 0).sum()),
                'complete_records': int(len(df.dropna()))
            },
            'feature_statistics': {
                'speed_range': [float(df['speed_mph'].min()), float(df['speed_mph'].max())],
                'volume_range': [float(df['volume_vehicles_per_hour'].min()), float(df['volume_vehicles_per_hour'].max())],
                'normalized_speed_range': [float(df['speed_normalized'].min()), float(df['speed_normalized'].max())],
                'normalized_volume_range': [float(df['volume_normalized'].min()), float(df['volume_normalized'].max())]
            },
            'categorical_distributions': {
                'road_types': {str(k): int(v) for k, v in df['road_type'].value_counts().to_dict().items()},
                'congestion_levels': {str(k): int(v) for k, v in df['congestion_level'].value_counts().to_dict().items()},
                'time_periods': {str(k): int(v) for k, v in df['time_period'].value_counts().to_dict().items()}
            }
        }
        
        # Check data quality
        quality_score = 100
        
        if validation_results['missing_values']['speed_mph'] > 0:
            quality_score -= 20
            logger.warning("Missing speed values detected")
        
        if validation_results['missing_values']['volume_vehicles_per_hour'] > 0:
            quality_score -= 20
            logger.warning("Missing volume values detected")
        
        if validation_results['missing_values']['derived_features'] > 0:
            quality_score -= 10
            logger.warning("Missing derived feature values detected")
        
        validation_results['quality_score'] = quality_score
        
        logger.info(f"✅ Validation complete - Quality Score: {quality_score}/100")
        return validation_results
    
    def save_processed_dataset(self, df: pd.DataFrame, validation_results: Dict) -> None:
        """Save the processed dataset and metadata"""
        logger.info("Saving processed dataset...")
        
        # Save main processed dataset
        processed_file = self.processed_dir / "metr_la_processed_data.csv"
        df.to_csv(processed_file, index=False)
        
        # Save lightweight version (essential columns only)
        essential_columns = [
            'timestamp', 'sensor_id', 'speed_mph', 'volume_vehicles_per_hour',
            'latitude', 'longitude', 'road_type', 'hour', 'day_of_week',
            'is_weekend', 'is_rush_hour', 'speed_normalized', 'volume_normalized',
            'traffic_density', 'congestion_level'
        ]
        
        df_essential = df[essential_columns].copy()
        essential_file = self.processed_dir / "metr_la_essential_features.csv"
        df_essential.to_csv(essential_file, index=False)
        
        # Save ML-ready dataset (numeric features only)
        ml_columns = [
            'sensor_id', 'timestamp', 'speed_mph', 'volume_vehicles_per_hour',
            'hour', 'day_of_week', 'is_weekend', 'is_rush_hour',
            'speed_normalized', 'volume_normalized', 'traffic_density',
            'road_type_encoded', 'time_period_encoded', 'congestion_level_encoded',
            'speed_1h_avg', 'volume_1h_avg', 'speed_3h_avg', 'volume_3h_avg'
        ]
        
        # Convert boolean columns to int for ML compatibility
        df_ml = df[ml_columns].copy()
        df_ml['is_weekend'] = df_ml['is_weekend'].astype(int)
        df_ml['is_rush_hour'] = df_ml['is_rush_hour'].astype(int)
        
        ml_file = self.processed_dir / "metr_la_ml_ready.csv"
        df_ml.to_csv(ml_file, index=False)
        
        # Save preprocessing metadata
        metadata = {
            'preprocessing_metadata': {
                'processed_date': datetime.now().isoformat(),
                'processor_version': '1.0',
                'input_files': [
                    'metr_la_sensor_metadata.csv',
                    'metr_la_traffic_data.csv or metr_la_sample_data.csv'
                ],
                'preprocessing_steps': [
                    'temporal_feature_extraction',
                    'missing_value_imputation',
                    'outlier_removal',
                    'feature_normalization',
                    'derived_feature_creation',
                    'categorical_encoding'
                ]
            },
            'output_files': {
                'full_processed': str(processed_file.name),
                'essential_features': str(essential_file.name),
                'ml_ready': str(ml_file.name)
            },
            'feature_descriptions': {
                'speed_normalized': 'Speed normalized by road type (0-1 scale)',
                'volume_normalized': 'Volume normalized by road type capacity (0-1 scale)',
                'traffic_density': 'Vehicles per lane per hour',
                'congestion_level': 'Traffic congestion classification (free_flow, moderate, heavy)',
                'time_period': 'Time classification (morning_rush, evening_rush, midday, late_night, other)',
                'speed_1h_avg': '1-hour rolling average speed',
                'volume_1h_avg': '1-hour rolling average volume',
                'speed_3h_avg': '3-hour rolling average speed',
                'volume_3h_avg': '3-hour rolling average volume'
            },
            'validation_results': validation_results
        }
        
        metadata_file = self.processed_dir / "preprocessing_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"✅ Processed dataset saved:")
        logger.info(f"   Full dataset: {processed_file} ({len(df):,} records)")
        logger.info(f"   Essential features: {essential_file} ({len(df_essential):,} records)")
        logger.info(f"   ML-ready: {ml_file} ({len(df_ml):,} records)")
        logger.info(f"   Metadata: {metadata_file}")
    
    def process_dataset(self) -> bool:
        """Main preprocessing pipeline"""
        try:
            logger.info("Starting METR-LA dataset preprocessing...")
            
            # Load data
            traffic_df, sensors_df = self.load_data()
            
            # Processing pipeline
            traffic_df = self.clean_temporal_data(traffic_df)
            traffic_df = self.handle_missing_values(traffic_df)
            traffic_df = self.remove_outliers(traffic_df)
            traffic_df = self.create_derived_features(traffic_df)
            
            # Validate results
            validation_results = self.validate_processed_data(traffic_df)
            
            # Save processed dataset
            self.save_processed_dataset(traffic_df, validation_results)
            
            logger.info("✅ METR-LA dataset preprocessing completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Preprocessing failed: {e}")
            return False

def main():
    """Main execution function"""
    print("=== METR-LA Dataset Preprocessing (Task 6.3) ===")
    print("Traffic Prediction System - Data Preprocessing\n")
    
    try:
        # Initialize preprocessor
        preprocessor = METRLAPreprocessor()
        
        # Process dataset
        success = preprocessor.process_dataset()
        
        if success:
            print("\n✅ Dataset preprocessing completed successfully!")
            print(f"📁 Processed files saved to: {preprocessor.processed_dir}")
            print("📊 Check preprocessing_metadata.json for detailed processing information")
            return True
        else:
            print("\n❌ Dataset preprocessing failed!")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)