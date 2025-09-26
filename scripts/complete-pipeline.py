#!/usr/bin/env python3
"""
Complete Traffic Data Processing and ML Pipeline
Downloads data from HDFS, processes it, trains ML models, and stores everything back in HDFS
"""

import json
import pandas as pd
import numpy as np
import logging
import os
import tempfile
import subprocess
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.preprocessing import StandardScaler, LabelEncoder
import joblib
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompleteTrafficPipeline:
    def __init__(self):
        """Initialize the complete traffic processing pipeline"""
        self.temp_dir = tempfile.mkdtemp()
        self.models = {}
        self.scalers = {}
        self.encoders = {}
        self.processed_data = {}
        
    def download_from_hdfs(self, hdfs_path: str, local_path: str):
        """Download file from HDFS"""
        logger.info(f"Downloading from HDFS: {hdfs_path}")
        
        try:
            # Download to container tmp
            cmd = f"docker exec namenode hdfs dfs -get {hdfs_path} /tmp/download_file"
            subprocess.run(cmd, shell=True, check=True)
            
            # Copy from container to local
            cmd = f"docker cp namenode:/tmp/download_file {local_path}"
            subprocess.run(cmd, shell=True, check=True)
            
            logger.info(f"Downloaded to: {local_path}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to download from HDFS: {e}")
            raise
    
    def upload_to_hdfs(self, local_path: str, hdfs_path: str):
        """Upload file to HDFS"""
        logger.info(f"Uploading to HDFS: {hdfs_path}")
        
        try:
            # Create HDFS directory
            hdfs_dir = "/".join(hdfs_path.split("/")[:-1])
            cmd = f"docker exec namenode hdfs dfs -mkdir -p {hdfs_dir}"
            subprocess.run(cmd, shell=True, check=True)
            
            # Copy local to container
            cmd = f"docker cp {local_path} namenode:/tmp/upload_file"
            subprocess.run(cmd, shell=True, check=True)
            
            # Upload to HDFS
            cmd = f"docker exec namenode hdfs dfs -put /tmp/upload_file {hdfs_path}"
            subprocess.run(cmd, shell=True, check=True)
            
            logger.info(f"Uploaded to HDFS: {hdfs_path}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to upload to HDFS: {e}")
            raise
    
    def load_and_process_raw_data(self):
        """Load and process raw traffic data"""
        logger.info("Loading and processing raw traffic data...")
        
        # Download raw data
        raw_data_local = os.path.join(self.temp_dir, "raw_data.jsonl")
        self.download_from_hdfs(
            "/traffic-data/raw/year=2025/month=09/day=19/metr-la-historical.jsonl",
            raw_data_local
        )
        
        # Load JSON data
        data_records = []
        with open(raw_data_local, 'r') as f:
            for line in f:
                data_records.append(json.loads(line.strip()))
        
        logger.info(f"Loaded {len(data_records)} raw traffic events")
        
        # Convert to DataFrame
        df = pd.json_normalize(data_records)
        
        logger.info(f"DataFrame shape: {df.shape}")
        logger.info(f"Columns: {list(df.columns)}")
        
        return df
    
    def create_hourly_aggregates(self, raw_df):
        """Create hourly traffic aggregates"""
        logger.info("Creating hourly traffic aggregates...")
        
        # Convert timestamp to datetime
        raw_df['timestamp'] = pd.to_datetime(raw_df['timestamp'])
        raw_df['hour_window'] = raw_df['timestamp'].dt.floor('H')
        
        # Group by sensor and hour
        aggregates = raw_df.groupby(['sensor_id', 'location.highway', 'hour_window', 'hour']).agg({
            'traffic_data.speed_mph': ['mean', 'min', 'max', 'std'],
            'traffic_data.volume_vehicles_per_hour': ['mean', 'sum', 'max'],
            'traffic_data.occupancy_percentage': ['mean', 'max'],
            'traffic_data.congestion_level': ['mean', 'max'],
            'weather.temperature_f': 'mean',
            'weather.precipitation': 'mean',
            'location.latitude': 'first',
            'location.longitude': 'first',
            'location.lanes': 'first',
            'is_weekend': 'first'
        }).reset_index()
        
        # Flatten column names
        new_columns = []
        for col in aggregates.columns:
            if isinstance(col, tuple):
                if col[1]:
                    new_columns.append('_'.join(col).strip())
                else:
                    new_columns.append(col[0])
            else:
                new_columns.append(col)
        aggregates.columns = new_columns
        
        # Calculate derived metrics
        aggregates['congestion_severity_ratio'] = (
            aggregates['traffic_data.congestion_level_mean'] / 10.0
        )
        
        aggregates['traffic_efficiency'] = (
            aggregates['traffic_data.speed_mph_mean'] / 
            (aggregates['traffic_data.occupancy_percentage_mean'] + 1)
        )
        
        aggregates['speed_variability'] = (
            aggregates['traffic_data.speed_mph_std'] / 
            aggregates['traffic_data.speed_mph_mean']
        ).fillna(0)
        
        # Add time features
        aggregates['hour_sin'] = np.sin(2 * np.pi * aggregates['hour'] / 24)
        aggregates['hour_cos'] = np.cos(2 * np.pi * aggregates['hour'] / 24)
        aggregates['is_rush_hour'] = (
            ((aggregates['hour'] >= 7) & (aggregates['hour'] <= 9)) |
            ((aggregates['hour'] >= 17) & (aggregates['hour'] <= 19))
        ).astype(int)
        
        logger.info(f"Created {len(aggregates)} hourly aggregates")
        
        self.processed_data['hourly_aggregates'] = aggregates
        return aggregates
    
    def prepare_ml_features(self, aggregates_df):
        """Prepare features for machine learning"""
        logger.info("Preparing ML features...")
        
        # Select and rename feature columns
        feature_columns = {
            'sensor_id': 'sensor_id',
            'location.highway': 'highway',
            'hour_window': 'hour_window',
            'traffic_data.speed_mph_mean': 'avg_speed_mph',
            'traffic_data.volume_vehicles_per_hour_mean': 'avg_volume_vph',
            'traffic_data.occupancy_percentage_mean': 'avg_occupancy',
            'traffic_data.congestion_level_mean': 'avg_congestion_level',
            'weather.temperature_f_mean': 'avg_temperature',
            'weather.precipitation_mean': 'precipitation_ratio',
            'location.latitude_first': 'latitude',
            'location.longitude_first': 'longitude',
            'is_weekend_first': 'is_weekend',
            'hour_sin': 'hour_sin',
            'hour_cos': 'hour_cos',
            'is_rush_hour': 'is_rush_hour',
            'congestion_severity_ratio': 'congestion_severity_ratio',
            'traffic_efficiency': 'traffic_efficiency',
            'speed_variability': 'speed_variability'
        }
        
        ml_features = aggregates_df[list(feature_columns.keys())].copy()
        ml_features = ml_features.rename(columns=feature_columns)
        
        # Handle missing values
        numeric_columns = ml_features.select_dtypes(include=[np.number]).columns
        ml_features[numeric_columns] = ml_features[numeric_columns].fillna(ml_features[numeric_columns].mean())
        
        # Encode categorical variables
        le_highway = LabelEncoder()
        ml_features['highway_encoded'] = le_highway.fit_transform(ml_features['highway'].fillna('Unknown'))
        self.encoders['highway'] = le_highway
        
        logger.info(f"ML features prepared - Shape: {ml_features.shape}")
        
        self.processed_data['ml_features'] = ml_features
        return ml_features
    
    def train_congestion_prediction_models(self, ml_features):
        """Train machine learning models for congestion prediction"""
        logger.info("Training congestion prediction models...")
        
        # Prepare features and target
        feature_cols = [
            'avg_volume_vph', 'avg_occupancy', 'avg_temperature', 'precipitation_ratio',
            'latitude', 'longitude', 'is_weekend', 'hour_sin', 'hour_cos', 
            'is_rush_hour', 'highway_encoded', 'traffic_efficiency', 'speed_variability'
        ]
        
        X = ml_features[feature_cols].copy()
        y_speed = ml_features['avg_speed_mph'].copy()
        y_congestion = ml_features['avg_congestion_level'].copy()
        
        # Handle any remaining missing values
        X = X.fillna(X.mean())
        y_speed = y_speed.fillna(y_speed.mean())
        y_congestion = y_congestion.fillna(y_congestion.mean())
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        self.scalers['features'] = scaler
        
        # Train models for speed prediction
        logger.info("Training Random Forest for speed prediction...")
        X_train, X_test, y_train_speed, y_test_speed = train_test_split(
            X_scaled, y_speed, test_size=0.2, random_state=42
        )
        
        # Random Forest for speed prediction
        rf_speed = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        rf_speed.fit(X_train, y_train_speed)
        
        # Gradient Boosting for speed prediction
        gb_speed = GradientBoostingRegressor(n_estimators=100, random_state=42)
        gb_speed.fit(X_train, y_train_speed)
        
        # Train models for congestion level prediction
        _, _, y_train_cong, y_test_cong = train_test_split(
            X_scaled, y_congestion, test_size=0.2, random_state=42
        )
        
        # Random Forest for congestion prediction
        rf_congestion = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        rf_congestion.fit(X_train, y_train_cong)
        
        # Store models
        self.models = {
            'random_forest_speed': rf_speed,
            'gradient_boosting_speed': gb_speed,
            'random_forest_congestion': rf_congestion
        }
        
        # Evaluate models
        self.evaluate_models(X_test, y_test_speed, y_test_cong)
        
        logger.info("Model training completed!")
        
    def evaluate_models(self, X_test, y_test_speed, y_test_congestion):
        """Evaluate trained models"""
        logger.info("Evaluating models...")
        
        results = {
            'model_performance': {},
            'feature_importance': {},
            'evaluation_timestamp': datetime.now().isoformat()
        }
        
        # Evaluate speed prediction models
        for model_name in ['random_forest_speed', 'gradient_boosting_speed']:
            model = self.models[model_name]
            y_pred = model.predict(X_test)
            
            mse = mean_squared_error(y_test_speed, y_pred)
            rmse = np.sqrt(mse)
            mae = mean_absolute_error(y_test_speed, y_pred)
            r2 = r2_score(y_test_speed, y_pred)
            
            results['model_performance'][model_name] = {
                'mse': float(mse),
                'rmse': float(rmse),
                'mae': float(mae),
                'r2_score': float(r2)
            }
            
            logger.info(f"{model_name} - RMSE: {rmse:.2f}, R²: {r2:.3f}")
        
        # Evaluate congestion prediction model
        model = self.models['random_forest_congestion']
        y_pred = model.predict(X_test)
        
        mse = mean_squared_error(y_test_congestion, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test_congestion, y_pred)
        r2 = r2_score(y_test_congestion, y_pred)
        
        results['model_performance']['random_forest_congestion'] = {
            'mse': float(mse),
            'rmse': float(rmse),
            'mae': float(mae),
            'r2_score': float(r2)
        }
        
        logger.info(f"Congestion model - RMSE: {rmse:.2f}, R²: {r2:.3f}")
        
        # Feature importance
        for model_name, model in self.models.items():
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                feature_names = [
                    'avg_volume_vph', 'avg_occupancy', 'avg_temperature', 'precipitation_ratio',
                    'latitude', 'longitude', 'is_weekend', 'hour_sin', 'hour_cos', 
                    'is_rush_hour', 'highway_encoded', 'traffic_efficiency', 'speed_variability'
                ]
                
                results['feature_importance'][model_name] = {
                    name: float(importance) 
                    for name, importance in zip(feature_names, importances)
                }
        
        self.processed_data['model_evaluation'] = results
        return results
    
    def save_models_to_hdfs(self):
        """Save trained models and metadata to HDFS"""
        logger.info("Saving models to HDFS...")
        
        # Save models locally first
        models_dir = os.path.join(self.temp_dir, 'models')
        os.makedirs(models_dir, exist_ok=True)
        
        # Save each model
        for model_name, model in self.models.items():
            model_file = os.path.join(models_dir, f'{model_name}.joblib')
            joblib.dump(model, model_file)
            
            # Upload to HDFS
            hdfs_path = f"/traffic-data/models/{model_name}.joblib"
            self.upload_to_hdfs(model_file, hdfs_path)
        
        # Save scalers
        for scaler_name, scaler in self.scalers.items():
            scaler_file = os.path.join(models_dir, f'scaler_{scaler_name}.joblib')
            joblib.dump(scaler, scaler_file)
            
            hdfs_path = f"/traffic-data/models/scaler_{scaler_name}.joblib"
            self.upload_to_hdfs(scaler_file, hdfs_path)
        
        # Save encoders
        for encoder_name, encoder in self.encoders.items():
            encoder_file = os.path.join(models_dir, f'encoder_{encoder_name}.joblib')
            joblib.dump(encoder, encoder_file)
            
            hdfs_path = f"/traffic-data/models/encoder_{encoder_name}.joblib"
            self.upload_to_hdfs(encoder_file, hdfs_path)
        
        # Save model metadata
        metadata = {
            'training_timestamp': datetime.now().isoformat(),
            'model_versions': {name: '1.0' for name in self.models.keys()},
            'feature_names': [
                'avg_volume_vph', 'avg_occupancy', 'avg_temperature', 'precipitation_ratio',
                'latitude', 'longitude', 'is_weekend', 'hour_sin', 'hour_cos', 
                'is_rush_hour', 'highway_encoded', 'traffic_efficiency', 'speed_variability'
            ],
            'target_variables': ['avg_speed_mph', 'avg_congestion_level'],
            'performance_metrics': self.processed_data.get('model_evaluation', {})
        }
        
        metadata_file = os.path.join(models_dir, 'model_metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.upload_to_hdfs(metadata_file, "/traffic-data/models/model_metadata.json")
        
        logger.info("Models saved to HDFS successfully!")
    
    def save_processed_data_to_hdfs(self):
        """Save processed datasets to HDFS"""
        logger.info("Saving processed datasets to HDFS...")
        
        # Save hourly aggregates
        if 'hourly_aggregates' in self.processed_data:
            agg_file = os.path.join(self.temp_dir, 'hourly_aggregates.csv')
            self.processed_data['hourly_aggregates'].to_csv(agg_file, index=False)
            
            hdfs_path = "/traffic-data/processed/aggregates/year=2025/month=09/day=19/hourly_aggregates.csv"
            self.upload_to_hdfs(agg_file, hdfs_path)
        
        # Save ML features
        if 'ml_features' in self.processed_data:
            ml_file = os.path.join(self.temp_dir, 'ml_features.csv')
            self.processed_data['ml_features'].to_csv(ml_file, index=False)
            
            hdfs_path = "/traffic-data/processed/ml-features/year=2025/month=09/day=19/ml_features.csv"
            self.upload_to_hdfs(ml_file, hdfs_path)
        
        logger.info("Processed datasets saved to HDFS!")
    
    def run_complete_pipeline(self):
        """Run the complete data processing and ML pipeline"""
        logger.info("Starting complete traffic data pipeline...")
        
        try:
            # Step 1: Load and process raw data
            raw_df = self.load_and_process_raw_data()
            
            # Step 2: Create hourly aggregates
            aggregates_df = self.create_hourly_aggregates(raw_df)
            
            # Step 3: Prepare ML features
            ml_features = self.prepare_ml_features(aggregates_df)
            
            # Step 4: Train ML models
            self.train_congestion_prediction_models(ml_features)
            
            # Step 5: Save processed data to HDFS
            self.save_processed_data_to_hdfs()
            
            # Step 6: Save models to HDFS
            self.save_models_to_hdfs()
            
            # Step 7: Show final summary
            self.show_final_summary()
            
            logger.info("Complete pipeline finished successfully!")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
    
    def show_final_summary(self):
        """Show final pipeline summary"""
        logger.info("=== PIPELINE COMPLETION SUMMARY ===")
        
        if 'hourly_aggregates' in self.processed_data:
            agg_count = len(self.processed_data['hourly_aggregates'])
            logger.info(f"✅ Hourly aggregates created: {agg_count:,}")
        
        if 'ml_features' in self.processed_data:
            ml_count = len(self.processed_data['ml_features'])
            logger.info(f"✅ ML feature records: {ml_count:,}")
        
        logger.info(f"✅ ML models trained: {len(self.models)}")
        
        if 'model_evaluation' in self.processed_data:
            perf = self.processed_data['model_evaluation']['model_performance']
            for model_name, metrics in perf.items():
                logger.info(f"   {model_name}: R² = {metrics['r2_score']:.3f}")
        
        logger.info("✅ All data and models saved to HDFS")
        logger.info("🎯 Traffic prediction system ready for deployment!")
    
    def cleanup(self):
        """Cleanup temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        logger.info("Cleanup completed")

def main():
    """Main entry point"""
    pipeline = CompleteTrafficPipeline()
    
    try:
        print("🚀 Starting Complete Traffic Data Pipeline")
        print("📊 Processing: Raw Data → Aggregates → ML Features → Trained Models")
        print("💾 Storage: Everything saved to HDFS")
        print("=" * 70)
        
        pipeline.run_complete_pipeline()
        
        print("✅ Complete pipeline finished successfully!")
        print("🎉 Your traffic prediction system is ready!")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return 1
    finally:
        pipeline.cleanup()
    
    return 0

if __name__ == "__main__":
    exit(main())