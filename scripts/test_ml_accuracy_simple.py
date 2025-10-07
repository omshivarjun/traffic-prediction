#!/usr/bin/env python3
"""
Simple ML Model Accuracy Test
Tests the retrained models against METR-LA dataset
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleMLTester:
    """Test ML models with actual METR-LA data"""
    
    def __init__(self):
        self.models = {}
        self.scaler = None
        self.encoder = None
        self.feature_names = None
        
    def load_data_from_hdfs(self, hdfs_path: str, limit: int = 10000) -> pd.DataFrame:
        """Load JSONL data from HDFS via docker"""
        try:
            logger.info(f"Loading data from HDFS: {hdfs_path}")
            
            # Download via docker cp (same method as retrain script)
            temp_docker_path = "/tmp/test_data.jsonl"
            local_temp_path = Path("temp_test_data.jsonl")
            
            # Copy from HDFS to docker container (suppress stderr)
            cmd1 = f"docker exec namenode hdfs dfs -get {hdfs_path} {temp_docker_path} 2>/dev/null"
            subprocess.run(cmd1, shell=True, check=False, capture_output=True)
            
            # Copy from docker to local
            cmd2 = f"docker cp namenode:{temp_docker_path} {local_temp_path}"
            subprocess.run(cmd2, shell=True, check=False, capture_output=True)
            
            # Parse JSONL
            with open(local_temp_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            data = [json.loads(line) for line in lines]
            df = pd.DataFrame(data)
            
            logger.info(f"✓ Loaded {len(df)} records from HDFS")
            
            # Sample if too large
            if len(df) > limit:
                df = df.sample(n=limit, random_state=42)
                logger.info(f"Sampled {limit} records for testing")
            
            # Cleanup
            local_temp_path.unlink(missing_ok=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare features exactly like training script"""
        try:
            logger.info("Preparing features...")
            
            # Extract nested fields
            if 'traffic_data' in df.columns:
                df['speed'] = df['traffic_data'].apply(lambda x: x.get('speed_mph') if isinstance(x, dict) else None)
                df['volume'] = df['traffic_data'].apply(lambda x: x.get('volume_vehicles_per_hour') if isinstance(x, dict) else None)
                df['occupancy'] = df['traffic_data'].apply(lambda x: x.get('occupancy_percentage') if isinstance(x, dict) else None)
                df = df.drop('traffic_data', axis=1)
            
            if 'location' in df.columns:
                df['highway'] = df['location'].apply(lambda x: x.get('highway') if isinstance(x, dict) else None)
                df = df.drop('location', axis=1)
            
            if 'weather' in df.columns:
                df = df.drop('weather', axis=1)
            
            # Convert timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values(['sensor_id', 'timestamp'])
            
            # Temporal features
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            df['day_of_month'] = df['timestamp'].dt.day
            df['month'] = df['timestamp'].dt.month
            df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
            df['is_morning_rush'] = ((df['hour'] >= 7) & (df['hour'] <= 9)).astype(int)
            df['is_evening_rush'] = ((df['hour'] >= 16) & (df['hour'] <= 18)).astype(int)
            
            # Lag features
            df['speed_lag_1'] = df.groupby('sensor_id')['speed'].shift(1)
            df['speed_lag_2'] = df.groupby('sensor_id')['speed'].shift(2)
            df['speed_lag_3'] = df.groupby('sensor_id')['speed'].shift(3)
            df['volume_lag_1'] = df.groupby('sensor_id')['volume'].shift(1)
            df['occupancy_lag_1'] = df.groupby('sensor_id')['occupancy'].shift(1)
            
            # Rolling stats
            df['speed_rolling_mean_3'] = df.groupby('sensor_id')['speed'].rolling(window=3, min_periods=1).mean().reset_index(level=0, drop=True)
            df['speed_rolling_std_3'] = df.groupby('sensor_id')['speed'].rolling(window=3, min_periods=1).std().reset_index(level=0, drop=True)
            
            # Fill NaN in rolling std with 0 (happens when std is undefined for small windows)
            df['speed_rolling_std_3'] = df['speed_rolling_std_3'].fillna(0)
            
            # Encode highway
            if 'highway' in df.columns and self.encoder is not None:
                df['highway_encoded'] = self.encoder.transform(df['highway'].fillna('unknown'))
            
            # Drop NaN lag features
            df = df.dropna(subset=['speed_lag_1'])
            
            # Feature columns (same as training)
            feature_cols = [
                'hour', 'day_of_week', 'day_of_month', 'month',
                'is_weekend', 'is_morning_rush', 'is_evening_rush',
                'speed_lag_1', 'speed_lag_2', 'speed_lag_3',
                'speed_rolling_mean_3', 'speed_rolling_std_3',
                'volume_lag_1', 'occupancy_lag_1', 'highway_encoded'
            ]
            
            # Filter existing
            feature_cols = [col for col in feature_cols if col in df.columns]
            
            X = df[feature_cols]
            y = df['speed']
            
            # Drop any remaining NaN values
            valid_mask = ~X.isna().any(axis=1)
            X = X[valid_mask]
            y = y[valid_mask]
            
            logger.info(f"✓ Prepared {len(X)} samples with {len(feature_cols)} features")
            
            return X, y
            
        except Exception as e:
            logger.error(f"Feature preparation failed: {e}")
            raise
    
    def load_models(self) -> bool:
        """Load models from HDFS"""
        try:
            logger.info("Loading models from HDFS...")
            
            model_files = [
                'random_forest_speed.joblib',
                'gradient_boosting_speed.joblib',
                'scaler_features.joblib',
                'encoder_highway.joblib'
            ]
            
            temp_dir = Path("temp_models")
            temp_dir.mkdir(exist_ok=True)
            
            for filename in model_files:
                hdfs_path = f"/traffic-data/models/{filename}"
                temp_docker = f"/tmp/{filename}"
                local_path = temp_dir / filename
                
                # HDFS → Docker (suppress stderr)
                cmd1 = f"docker exec namenode hdfs dfs -get {hdfs_path} {temp_docker} 2>/dev/null"
                result1 = subprocess.run(cmd1, shell=True, capture_output=True)
                
                # Docker → Local
                cmd2 = f"docker cp namenode:{temp_docker} {local_path}"
                result2 = subprocess.run(cmd2, shell=True, capture_output=True)
                
                # Load
                if 'scaler' in filename:
                    self.scaler = joblib.load(local_path)
                elif 'encoder' in filename:
                    self.encoder = joblib.load(local_path)
                else:
                    model_name = filename.replace('.joblib', '')
                    self.models[model_name] = joblib.load(local_path)
                
                logger.info(f"✓ Loaded {filename}")
            
            logger.info(f"✓ All models loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Model loading failed: {e}")
            return False
    
    def test_accuracy(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """Test model accuracy"""
        try:
            logger.info("\n" + "="*80)
            logger.info("TESTING MODEL ACCURACY")
            logger.info("="*80)
            
            # Scale features
            X_scaled = self.scaler.transform(X)
            
            results = {}
            
            for model_name, model in self.models.items():
                logger.info(f"\nTesting {model_name}...")
                
                # Predict
                y_pred = model.predict(X_scaled)
                
                # Metrics
                mae = mean_absolute_error(y, y_pred)
                rmse = np.sqrt(mean_squared_error(y, y_pred))
                r2 = r2_score(y, y_pred)
                
                results[model_name] = {
                    'mae': float(mae),
                    'rmse': float(rmse),
                    'r2': float(r2)
                }
                
                logger.info(f"  MAE:  {mae:.2f} mph")
                logger.info(f"  RMSE: {rmse:.2f} mph")
                logger.info(f"  R²:   {r2:.4f}")
                
                # Safety assessment
                if mae < 5:
                    logger.info(f"  ✓ EXCELLENT - Safe for production")
                elif mae < 10:
                    logger.info(f"  ✓ ACCEPTABLE - Deploy with monitoring")
                else:
                    logger.error(f"  ✗ POOR - Retrain with more data")
            
            return results
            
        except Exception as e:
            logger.error(f"Accuracy testing failed: {e}")
            raise


def main():
    """Main test execution"""
    try:
        logger.info("\n" + "="*80)
        logger.info("SAFETY-CRITICAL: ML MODEL ACCURACY TEST")
        logger.info("="*80 + "\n")
        
        tester = SimpleMLTester()
        
        # 1. Load models
        if not tester.load_models():
            logger.error("✗ Failed to load models")
            return 1
        
        # 2. Load test data
        hdfs_path = "/traffic-data/raw/year=2025/month=09/day=19/metr-la-historical.jsonl"
        df = tester.load_data_from_hdfs(hdfs_path, limit=10000)
        
        if df.empty:
            logger.error("✗ No test data loaded")
            return 1
        
        # 3. Prepare features
        X, y = tester.prepare_features(df)
        
        # 4. Test accuracy
        results = tester.test_accuracy(X, y)
        
        # 5. Save results
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"ml_accuracy_simple_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'test_samples': len(X),
                'results': results,
                'status': 'SUCCESS'
            }, f, indent=2)
        
        logger.info(f"\n✓ Results saved to: {output_file}")
        logger.info("\n" + "="*80)
        logger.info("✓ ACCURACY TESTING COMPLETE")
        logger.info("="*80)
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
