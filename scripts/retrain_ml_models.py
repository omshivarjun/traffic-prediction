#!/usr/bin/env python3
"""
METR-LA ML Model Retraining Script
===================================

Retrains ML models with current library versions (NumPy 1.26.4, scikit-learn 1.7.2)
to fix compatibility issues with old pickled models.

This script:
1. Loads METR-LA data from HDFS
2. Performs feature engineering
3. Trains RandomForest and GradientBoosting models
4. Exports models to HDFS in current format
5. Generates model metadata

Author: AI Assistant
Date: 2025-10-05
Priority: CRITICAL - Blocks ML accuracy testing
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetrLAModelTrainer:
    """Trains ML models for traffic speed prediction using METR-LA dataset"""
    
    def __init__(self, hdfs_data_path: str = "/traffic-data/raw/year=2025/month=09/day=19/metr-la-historical.jsonl"):
        """
        Initialize the trainer
        
        Args:
            hdfs_data_path: Path to METR-LA data in HDFS
        """
        self.hdfs_data_path = hdfs_data_path
        self.models = {}
        self.scalers = {}
        self.encoders = {}
        self.feature_names = []
        
        logger.info("MetrLAModelTrainer initialized")
        logger.info(f"HDFS data path: {hdfs_data_path}")
    
    def load_data_from_hdfs(self) -> pd.DataFrame:
        """
        Load METR-LA data from HDFS
        
        Returns:
            DataFrame with traffic data
        """
        try:
            logger.info(f"Loading data from HDFS: {self.hdfs_data_path}")
            
            # Create temp file for download
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.jsonl', delete=False) as tmp_file:
                local_path = tmp_file.name
            
            # Download from HDFS using docker cp method
            temp_docker_path = "/tmp/metr_la_training_data.jsonl"
            
            # Step 1: Download to docker temp
            cmd1 = f"docker exec namenode hdfs dfs -get {self.hdfs_data_path} {temp_docker_path}"
            result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
            
            if result1.returncode != 0:
                raise Exception(f"Failed to download from HDFS: {result1.stderr}")
            
            # Step 2: Copy from docker to local
            cmd2 = f"docker cp namenode:{temp_docker_path} {local_path}"
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
            
            if result2.returncode != 0:
                raise Exception(f"Failed to copy from docker: {result2.stderr}")
            
            # Step 3: Cleanup docker temp
            subprocess.run(f"docker exec namenode rm {temp_docker_path}", shell=True, capture_output=True)
            
            # Parse JSONL data
            logger.info("Parsing JSONL data...")
            lines = []
            with open(local_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            lines.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            
            df = pd.DataFrame(lines)
            
            # Cleanup local temp file
            os.unlink(local_path)
            
            logger.info(f"✓ Loaded {len(df)} records from HDFS")
            logger.info(f"Columns: {df.columns.tolist()}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load data from HDFS: {e}")
            raise
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare features for ML training
        
        Args:
            df: Raw traffic data
            
        Returns:
            Tuple of (features_df, target_series)
        """
        try:
            logger.info("Preparing features for ML training...")
            
            # Extract nested traffic_data fields
            logger.info("Extracting nested traffic_data fields...")
            if 'traffic_data' in df.columns:
                df['speed'] = df['traffic_data'].apply(lambda x: x.get('speed_mph') if isinstance(x, dict) else None)
                df['volume'] = df['traffic_data'].apply(lambda x: x.get('volume_vehicles_per_hour') if isinstance(x, dict) else None)
                df['occupancy'] = df['traffic_data'].apply(lambda x: x.get('occupancy_percentage') if isinstance(x, dict) else None)
                df['congestion_level'] = df['traffic_data'].apply(lambda x: x.get('congestion_level') if isinstance(x, dict) else None)
                logger.info(f"✓ Extracted: speed, volume, occupancy, congestion_level")
                
                # Drop the nested column
                df = df.drop('traffic_data', axis=1)
            
            # Extract nested location fields
            if 'location' in df.columns:
                logger.info("Extracting nested location fields...")
                df['highway'] = df['location'].apply(lambda x: x.get('highway') if isinstance(x, dict) else None)
                df['direction'] = df['location'].apply(lambda x: x.get('direction') if isinstance(x, dict) else None)
                df['lanes'] = df['location'].apply(lambda x: x.get('lanes') if isinstance(x, dict) else None)
                logger.info(f"✓ Extracted: highway, direction, lanes")
                
                # Drop the nested column
                df = df.drop('location', axis=1)
            
            # Extract nested weather fields if needed
            if 'weather' in df.columns:
                logger.info("Extracting nested weather fields...")
                df['weather_condition'] = df['weather'].apply(lambda x: x.get('condition') if isinstance(x, dict) else None)
                df['temperature'] = df['weather'].apply(lambda x: x.get('temperature_f') if isinstance(x, dict) else None)
                df['precipitation'] = df['weather'].apply(lambda x: int(x.get('precipitation', False)) if isinstance(x, dict) else 0)
                logger.info(f"✓ Extracted: weather_condition, temperature, precipitation")
                
                # Drop the nested column
                df = df.drop('weather', axis=1)
            
            # Convert timestamp to datetime if string
            if 'timestamp' in df.columns and df['timestamp'].dtype == 'object':
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Sort by sensor and timestamp for lag features
            if 'sensor_id' in df.columns:
                df = df.sort_values(['sensor_id', 'timestamp'])
            else:
                df = df.sort_values('timestamp')
            
            # Extract temporal features
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            df['day_of_month'] = df['timestamp'].dt.day
            df['month'] = df['timestamp'].dt.month
            df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
            
            # Rush hour indicators
            df['is_morning_rush'] = ((df['hour'] >= 7) & (df['hour'] <= 9)).astype(int)
            df['is_evening_rush'] = ((df['hour'] >= 16) & (df['hour'] <= 18)).astype(int)
            
            # Create lag features (previous speed values)
            if 'sensor_id' in df.columns:
                df['speed_lag_1'] = df.groupby('sensor_id')['speed'].shift(1)
                df['speed_lag_2'] = df.groupby('sensor_id')['speed'].shift(2)
                df['speed_lag_3'] = df.groupby('sensor_id')['speed'].shift(3)
                
                # Rolling statistics
                df['speed_rolling_mean_3'] = df.groupby('sensor_id')['speed'].rolling(window=3, min_periods=1).mean().reset_index(level=0, drop=True)
                df['speed_rolling_std_3'] = df.groupby('sensor_id')['speed'].rolling(window=3, min_periods=1).std().reset_index(level=0, drop=True)
            else:
                df['speed_lag_1'] = df['speed'].shift(1)
                df['speed_lag_2'] = df['speed'].shift(2)
                df['speed_lag_3'] = df['speed'].shift(3)
                df['speed_rolling_mean_3'] = df['speed'].rolling(window=3, min_periods=1).mean()
                df['speed_rolling_std_3'] = df['speed'].rolling(window=3, min_periods=1).std()
            
            # Traffic volume features if available
            if 'volume' in df.columns:
                df['volume_lag_1'] = df.groupby('sensor_id')['volume'].shift(1) if 'sensor_id' in df.columns else df['volume'].shift(1)
            
            # Occupancy features if available
            if 'occupancy' in df.columns:
                df['occupancy_lag_1'] = df.groupby('sensor_id')['occupancy'].shift(1) if 'sensor_id' in df.columns else df['occupancy'].shift(1)
            
            # Handle highway/location encoding if present
            if 'highway' in df.columns:
                logger.info("Encoding highway field...")
                self.encoders['highway'] = LabelEncoder()
                df['highway_encoded'] = self.encoders['highway'].fit_transform(df['highway'].fillna('unknown'))
            
            # Drop rows with NaN in lag features (first few rows)
            df = df.dropna(subset=['speed_lag_1'])
            
            # Define feature columns
            feature_cols = [
                'hour', 'day_of_week', 'day_of_month', 'month',
                'is_weekend', 'is_morning_rush', 'is_evening_rush',
                'speed_lag_1', 'speed_lag_2', 'speed_lag_3',
                'speed_rolling_mean_3', 'speed_rolling_std_3'
            ]
            
            # Add volume/occupancy if available
            if 'volume_lag_1' in df.columns:
                feature_cols.append('volume_lag_1')
            if 'occupancy_lag_1' in df.columns:
                feature_cols.append('occupancy_lag_1')
            if 'highway_encoded' in df.columns:
                feature_cols.append('highway_encoded')
            
            # Filter to existing columns
            feature_cols = [col for col in feature_cols if col in df.columns]
            
            self.feature_names = feature_cols
            logger.info(f"Using {len(feature_cols)} features: {feature_cols}")
            
            # Prepare X and y
            X = df[feature_cols].copy()
            y = df['speed'].copy()
            
            # Handle any remaining NaNs
            X = X.fillna(0)
            
            logger.info(f"✓ Features prepared: {X.shape[0]} samples, {X.shape[1]} features")
            logger.info(f"Target (speed) range: {y.min():.1f} - {y.max():.1f} mph (mean: {y.mean():.1f})")
            
            return X, y
            
        except Exception as e:
            logger.error(f"Failed to prepare features: {e}")
            raise
    
    def train_models(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """
        Train ML models for speed prediction
        
        Args:
            X: Feature DataFrame
            y: Target Series (speed)
            
        Returns:
            Dictionary with training results
        """
        try:
            logger.info("\n" + "="*80)
            logger.info("TRAINING ML MODELS FOR SPEED PREDICTION")
            logger.info("="*80 + "\n")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            logger.info(f"Training set: {X_train.shape[0]} samples")
            logger.info(f"Test set: {X_test.shape[0]} samples")
            
            # Scale features
            logger.info("\nScaling features...")
            self.scalers['features'] = StandardScaler()
            X_train_scaled = self.scalers['features'].fit_transform(X_train)
            X_test_scaled = self.scalers['features'].transform(X_test)
            
            results = {}
            
            # Train RandomForestRegressor
            logger.info("\n" + "-"*80)
            logger.info("Training RandomForestRegressor...")
            logger.info("-"*80)
            
            rf_model = RandomForestRegressor(
                n_estimators=100,
                max_depth=20,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1,
                verbose=1
            )
            
            rf_model.fit(X_train_scaled, y_train)
            rf_pred = rf_model.predict(X_test_scaled)
            
            rf_mae = mean_absolute_error(y_test, rf_pred)
            rf_rmse = np.sqrt(mean_squared_error(y_test, rf_pred))
            rf_r2 = r2_score(y_test, rf_pred)
            
            self.models['random_forest_speed'] = rf_model
            
            logger.info(f"✓ RandomForest trained successfully")
            logger.info(f"  MAE:  {rf_mae:.2f} mph")
            logger.info(f"  RMSE: {rf_rmse:.2f} mph")
            logger.info(f"  R²:   {rf_r2:.4f}")
            
            results['random_forest'] = {
                'mae': rf_mae,
                'rmse': rf_rmse,
                'r2': rf_r2,
                'n_estimators': 100
            }
            
            # Train GradientBoostingRegressor
            logger.info("\n" + "-"*80)
            logger.info("Training GradientBoostingRegressor...")
            logger.info("-"*80)
            
            gb_model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=10,
                learning_rate=0.1,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                verbose=1
            )
            
            gb_model.fit(X_train_scaled, y_train)
            gb_pred = gb_model.predict(X_test_scaled)
            
            gb_mae = mean_absolute_error(y_test, gb_pred)
            gb_rmse = np.sqrt(mean_squared_error(y_test, gb_pred))
            gb_r2 = r2_score(y_test, gb_pred)
            
            self.models['gradient_boosting_speed'] = gb_model
            
            logger.info(f"✓ GradientBoosting trained successfully")
            logger.info(f"  MAE:  {gb_mae:.2f} mph")
            logger.info(f"  RMSE: {gb_rmse:.2f} mph")
            logger.info(f"  R²:   {gb_r2:.4f}")
            
            results['gradient_boosting'] = {
                'mae': gb_mae,
                'rmse': gb_rmse,
                'r2': gb_r2,
                'n_estimators': 100
            }
            
            # Create congestion classifier (RandomForest)
            logger.info("\n" + "-"*80)
            logger.info("Training RandomForest for congestion classification...")
            logger.info("-"*80)
            
            # Define congestion levels based on speed
            y_congestion = pd.cut(
                y_train, 
                bins=[0, 30, 50, 120], 
                labels=[2, 1, 0]  # 2=heavy, 1=moderate, 0=free-flow
            ).astype(int)
            
            y_congestion_test = pd.cut(
                y_test,
                bins=[0, 30, 50, 120],
                labels=[2, 1, 0]
            ).astype(int)
            
            congestion_model = RandomForestRegressor(
                n_estimators=100,
                max_depth=15,
                random_state=42,
                n_jobs=-1
            )
            
            congestion_model.fit(X_train_scaled, y_congestion)
            congestion_pred = congestion_model.predict(X_test_scaled)
            
            congestion_mae = mean_absolute_error(y_congestion_test, congestion_pred)
            congestion_r2 = r2_score(y_congestion_test, congestion_pred)
            
            self.models['random_forest_congestion'] = congestion_model
            
            logger.info(f"✓ Congestion classifier trained successfully")
            logger.info(f"  MAE:  {congestion_mae:.2f}")
            logger.info(f"  R²:   {congestion_r2:.4f}")
            
            results['congestion'] = {
                'mae': congestion_mae,
                'r2': congestion_r2
            }
            
            # Summary
            logger.info("\n" + "="*80)
            logger.info("TRAINING COMPLETE")
            logger.info("="*80)
            logger.info(f"\nBest Speed Model: {'RandomForest' if rf_mae < gb_mae else 'GradientBoosting'}")
            logger.info(f"Best MAE: {min(rf_mae, gb_mae):.2f} mph")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to train models: {e}")
            raise
    
    def export_models_to_hdfs(self, hdfs_models_path: str = "/traffic-data/models/") -> bool:
        """
        Export trained models to HDFS
        
        Args:
            hdfs_models_path: HDFS path to save models
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"\nExporting models to HDFS: {hdfs_models_path}")
            
            # Create temp directory for models
            temp_dir = Path(tempfile.mkdtemp())
            logger.info(f"Using temp directory: {temp_dir}")
            
            # Save models locally first
            models_to_save = {
                'random_forest_speed.joblib': self.models['random_forest_speed'],
                'gradient_boosting_speed.joblib': self.models['gradient_boosting_speed'],
                'random_forest_congestion.joblib': self.models['random_forest_congestion'],
                'scaler_features.joblib': self.scalers['features']
            }
            
            if 'highway' in self.encoders:
                models_to_save['encoder_highway.joblib'] = self.encoders['highway']
            
            for filename, model in models_to_save.items():
                local_path = temp_dir / filename
                joblib.dump(model, local_path)
                logger.info(f"✓ Saved {filename} locally ({local_path.stat().st_size / 1024:.1f} KB)")
            
            # Create metadata
            metadata = {
                'training_date': datetime.now().isoformat(),
                'numpy_version': np.__version__,
                'sklearn_version': '1.7.2',  # Current version
                'feature_names': self.feature_names,
                'models': list(models_to_save.keys()),
                'training_samples': len(self.feature_names)
            }
            
            metadata_path = temp_dir / 'model_metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"✓ Saved metadata")
            
            # Upload to HDFS
            logger.info("\nUploading to HDFS...")
            
            # Remove old models directory
            cmd_rm = f"docker exec namenode hdfs dfs -rm -r {hdfs_models_path}"
            subprocess.run(cmd_rm, shell=True, capture_output=True)
            
            # Create new directory
            cmd_mkdir = f"docker exec namenode hdfs dfs -mkdir -p {hdfs_models_path}"
            result = subprocess.run(cmd_mkdir, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"Directory creation warning: {result.stderr}")
            
            # Upload each file
            for filename in list(models_to_save.keys()) + ['model_metadata.json']:
                local_path = temp_dir / filename
                temp_docker_path = f"/tmp/{filename}"
                hdfs_path = f"{hdfs_models_path}{filename}"
                
                # Step 1: Copy to docker
                cmd1 = f"docker cp {local_path} namenode:{temp_docker_path}"
                result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
                
                if result1.returncode != 0:
                    raise Exception(f"Failed to copy {filename} to docker: {result1.stderr}")
                
                # Step 2: Upload to HDFS
                cmd2 = f"docker exec namenode hdfs dfs -put {temp_docker_path} {hdfs_path}"
                result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
                
                if result2.returncode != 0:
                    raise Exception(f"Failed to upload {filename} to HDFS: {result2.stderr}")
                
                # Step 3: Cleanup docker temp
                subprocess.run(f"docker exec namenode rm {temp_docker_path}", shell=True, capture_output=True)
                
                logger.info(f"✓ Uploaded {filename} to HDFS")
            
            # Verify upload
            cmd_verify = f"docker exec namenode hdfs dfs -ls {hdfs_models_path}"
            result = subprocess.run(cmd_verify, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("\nVerified HDFS models:")
                logger.info(result.stdout)
            
            logger.info("\n" + "="*80)
            logger.info("✓ ALL MODELS EXPORTED TO HDFS SUCCESSFULLY")
            logger.info("="*80)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to export models to HDFS: {e}")
            raise


def main():
    """Main training pipeline"""
    try:
        logger.info("\n" + "="*80)
        logger.info("METR-LA ML MODEL RETRAINING")
        logger.info("="*80)
        logger.info(f"NumPy version: {np.__version__}")
        logger.info(f"Start time: {datetime.now()}")
        
        # Initialize trainer
        trainer = MetrLAModelTrainer()
        
        # Load data from HDFS
        df = trainer.load_data_from_hdfs()
        
        # Prepare features
        X, y = trainer.prepare_features(df)
        
        # Train models
        results = trainer.train_models(X, y)
        
        # Export to HDFS
        trainer.export_models_to_hdfs()
        
        logger.info("\n" + "="*80)
        logger.info("✓ TRAINING PIPELINE COMPLETE")
        logger.info("="*80)
        logger.info(f"End time: {datetime.now()}")
        logger.info("\nNext step: Run 'python scripts\\test_ml_accuracy.py' to verify model accuracy")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ TRAINING FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
