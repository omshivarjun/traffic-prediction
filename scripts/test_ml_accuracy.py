"""
SAFETY-CRITICAL: ML Model Accuracy Testing
===========================================
Tests trained ML models on METR-LA dataset to verify prediction accuracy.

CRITICAL: Predictions must be ACCURATE, not just safe. Safe bounds prevent
dangerous outputs, but don't guarantee correct predictions.

User's Concern: "accidents will happen due to wrong predictions"
This test verifies predictions are CORRECT, not just within safe ranges.
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Hadoop/Spark imports
from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
import joblib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MLModelTester:
    """
    SAFETY-CRITICAL: Test ML model accuracy on real traffic data
    
    Verifies that predictions are not just safe (within bounds)
    but also ACCURATE (match actual traffic conditions).
    """
    
    # Accuracy thresholds
    TARGET_MAE = 5.0  # Mean Absolute Error <5 mph acceptable
    TARGET_RMSE = 8.0  # Root Mean Square Error <8 mph acceptable
    TARGET_R2 = 0.7  # R² score >0.7 acceptable (70% variance explained)
    
    # Warning thresholds
    WARNING_MAE = 10.0  # MAE >10 mph is concerning
    WARNING_RMSE = 15.0  # RMSE >15 mph is concerning
    WARNING_R2 = 0.5  # R² <0.5 is poor
    
    def __init__(self, hdfs_models_path: str = "/traffic-data/models/"):
        """
        Initialize ML model tester
        
        Args:
            hdfs_models_path: HDFS path to trained models
        """
        self.hdfs_models_path = hdfs_models_path
        self.spark = self._create_spark_session()
        self.models = {}
        self.test_results = {}
        
        logger.info("MLModelTester initialized")
    
    def _create_spark_session(self) -> SparkSession:
        """Create Spark session for HDFS access"""
        return SparkSession.builder \
            .appName("MLModelAccuracyTesting") \
            .master("local[*]") \
            .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
            .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
            .getOrCreate()
    
    def load_models_from_hdfs(self) -> bool:
        """
        Load trained ML models from HDFS
        
        Returns:
            True if models loaded successfully
        """
        try:
            logger.info(f"Loading models from HDFS: {self.hdfs_models_path}")
            
            # Check HDFS connectivity
            sc = self.spark.sparkContext
            hadoop_conf = sc._jsc.hadoopConfiguration()
            
            # Create local temp directory for model download
            local_models_dir = Path("./temp_models")
            local_models_dir.mkdir(exist_ok=True)
            
            # Download models from HDFS
            models_to_load = [
                "random_forest_speed.joblib",
                "gradient_boosting_speed.joblib",
                "random_forest_congestion.joblib",
                "scaler_features.joblib",
                "encoder_highway.joblib",
                "model_metadata.json"
            ]
            
            for model_file in models_to_load:
                hdfs_path = f"{self.hdfs_models_path}{model_file}"
                local_path = local_models_dir / model_file
                
                logger.info(f"Downloading {model_file} from HDFS...")
                
                # Use hdfs command to download directly to file
                import subprocess
                # Use Windows path for docker volume
                temp_docker_path = f"/tmp/{model_file}"
                
                # Download to docker temp first, then copy out
                cmd1 = f"docker exec namenode hdfs dfs -get {hdfs_path} {temp_docker_path}"
                result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
                
                if result1.returncode != 0:
                    logger.error(f"✗ Failed to download {model_file} from HDFS: {result1.stderr}")
                    return False
                
                # Copy from docker to local
                cmd2 = f"docker cp namenode:{temp_docker_path} {local_path}"
                result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
                
                if result2.returncode != 0:
                    logger.error(f"✗ Failed to copy {model_file} from docker: {result2.stderr}")
                    return False
                
                logger.info(f"✓ Downloaded {model_file}")
                
                # Clean up docker temp file
                subprocess.run(f"docker exec namenode rm {temp_docker_path}", shell=True)
            
            # Load models
            logger.info("Loading models into memory...")
            
            # Comprehensive NumPy backward compatibility fix
            # This handles models trained with older NumPy versions
            import numpy as np
            from types import ModuleType
            
            # Create _mt19937 module if it doesn't exist
            if 'numpy.random._mt19937' not in sys.modules:
                mt_module = ModuleType('numpy.random._mt19937')
                mt_module.MT19937 = np.random.MT19937
                sys.modules['numpy.random._mt19937'] = mt_module
            
            # Patch numpy.random._pickle for joblib compatibility
            if hasattr(np.random, '_pickle'):
                import numpy.random._pickle as np_pickle
                
                # Use getattr to avoid name mangling
                original_func = getattr(np_pickle, '__bit_generator_ctor', None)
                
                def patched_bit_gen_ctor(bit_gen_name):
                    # Handle old-style class references
                    if str(bit_gen_name) == "<class 'numpy.random._mt19937.MT19937'>":
                        return np.random.MT19937
                    # Fall back to original if available
                    if original_func:
                        return original_func(bit_gen_name)
                    # Default to MT19937
                    return np.random.MT19937
                
                np_pickle.__bit_generator_ctor = patched_bit_gen_ctor
            
            self.models['random_forest_speed'] = joblib.load(
                local_models_dir / "random_forest_speed.joblib"
            )
            self.models['gradient_boosting_speed'] = joblib.load(
                local_models_dir / "gradient_boosting_speed.joblib"
            )
            self.models['random_forest_congestion'] = joblib.load(
                local_models_dir / "random_forest_congestion.joblib"
            )
            self.models['scaler'] = joblib.load(
                local_models_dir / "scaler_features.joblib"
            )
            self.models['encoder'] = joblib.load(
                local_models_dir / "encoder_highway.joblib"
            )
            
            # Load metadata
            with open(local_models_dir / "model_metadata.json", 'r') as f:
                self.models['metadata'] = json.load(f)
            
            logger.info(f"✓ Loaded {len(self.models)} models/artifacts successfully")
            logger.info(f"Model metadata: {json.dumps(self.models['metadata'], indent=2)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load models: {str(e)}", exc_info=True)
            return False
    
    def load_metr_la_test_data(self, limit: int = 10000) -> pd.DataFrame:
        """
        Load METR-LA test dataset from HDFS
        
        Args:
            limit: Maximum number of records to load for testing
        
        Returns:
            DataFrame with test data
        """
        try:
            logger.info("Loading METR-LA test data from HDFS...")
            
            # Try processed features first
            hdfs_features_path = "/traffic-data/processed/ml-features/year=2025/month=09/day=19/ml_features.csv"
            
            logger.info(f"Reading features from: {hdfs_features_path}")
            
            # Download features file via docker
            import subprocess
            temp_docker_path = "/tmp/ml_features.csv"
            local_temp_path = Path("./temp_models/ml_features.csv")
            
            # Download to docker temp
            cmd1 = f"docker exec namenode hdfs dfs -get {hdfs_features_path} {temp_docker_path}"
            result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
            
            if result1.returncode != 0:
                logger.error(f"Failed to load features: {result1.stderr}")
                
                # Try raw METR-LA data
                hdfs_raw_path = "/traffic-data/raw/year=2025/month=09/day=19/metr-la-historical.jsonl"
                logger.info(f"Trying raw data: {hdfs_raw_path}")
                
                temp_docker_path = "/tmp/metr_la_raw.jsonl"
                cmd1 = f"docker exec namenode hdfs dfs -get {hdfs_raw_path} {temp_docker_path}"
                result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
                
                if result1.returncode != 0:
                    raise Exception(f"No test data found: {result1.stderr}")
                
                # Copy from docker
                cmd2 = f"docker cp namenode:{temp_docker_path} {local_temp_path}"
                result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
                
                # Parse JSONL data
                lines = []
                with open(local_temp_path, 'r') as f:
                    lines = [line.strip() for line in f if line.strip()]
                
                data = [json.loads(line) for line in lines]
                df = pd.DataFrame(data)
                
                logger.info(f"Loaded {len(df)} raw records")
            else:
                # Copy CSV from docker
                cmd2 = f"docker cp namenode:{temp_docker_path} {local_temp_path}"
                result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
                
                # Parse CSV data
                df = pd.read_csv(local_temp_path)
                logger.info(f"Loaded {len(df)} feature records")
            
            # Limit data size
            if len(df) > limit:
                df = df.sample(n=limit, random_state=42)
                logger.info(f"Sampled {limit} records for testing")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load test data: {str(e)}", exc_info=True)
            return pd.DataFrame()
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare features for ML model testing
        
        Args:
            df: Raw DataFrame with traffic data
        
        Returns:
            Tuple of (X_features, y_actual_speeds)
        """
        try:
            # Expected features based on model metadata
            required_features = [
                'speed_current',
                'volume',
                'occupancy',
                'hour_of_day',
                'day_of_week',
                'is_weekend',
                'speed_lag_1',
                'speed_lag_2',
                'speed_lag_3',
                'volume_lag_1',
                'volume_lag_2',
                'occupancy_lag_1'
            ]
            
            # Check which features exist
            available_features = [f for f in required_features if f in df.columns]
            missing_features = set(required_features) - set(available_features)
            
            if missing_features:
                logger.warning(f"Missing features: {missing_features}")
                logger.info("Will create synthetic features for testing")
                
                # Create synthetic features if missing
                if 'hour_of_day' not in df.columns and 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df['hour_of_day'] = df['timestamp'].dt.hour
                    df['day_of_week'] = df['timestamp'].dt.dayofweek
                    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
                
                # Create lag features if missing
                for lag in [1, 2, 3]:
                    if f'speed_lag_{lag}' not in df.columns and 'speed' in df.columns:
                        df[f'speed_lag_{lag}'] = df['speed'].shift(lag).fillna(df['speed'].mean())
                    if f'volume_lag_{lag}' not in df.columns and 'volume' in df.columns and lag <= 2:
                        df[f'volume_lag_{lag}'] = df['volume'].shift(lag).fillna(df['volume'].mean())
                
                if 'occupancy_lag_1' not in df.columns and 'occupancy' in df.columns:
                    df['occupancy_lag_1'] = df['occupancy'].shift(1).fillna(df['occupancy'].mean())
                
                # Use current speed as feature if speed_current missing
                if 'speed_current' not in df.columns and 'speed' in df.columns:
                    df['speed_current'] = df['speed']
            
            # Get features that actually exist
            available_features = [f for f in required_features if f in df.columns]
            
            if not available_features:
                raise ValueError("No usable features found in dataset")
            
            X = df[available_features].fillna(0).values
            
            # Get actual speeds (ground truth)
            if 'speed' in df.columns:
                y = df['speed'].values
            elif 'speed_current' in df.columns:
                y = df['speed_current'].values
            else:
                raise ValueError("No ground truth speed column found")
            
            # Remove any NaN/inf values
            valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y) | np.isinf(y))
            X = X[valid_mask]
            y = y[valid_mask]
            
            logger.info(f"Prepared features: {X.shape}, ground truth: {y.shape}")
            logger.info(f"Features used: {available_features}")
            logger.info(f"Speed range: {y.min():.1f} - {y.max():.1f} mph (mean: {y.mean():.1f})")
            
            return X, y
            
        except Exception as e:
            logger.error(f"Failed to prepare features: {str(e)}", exc_info=True)
            return np.array([]), np.array([])
    
    def test_model_accuracy(
        self,
        model_name: str,
        X_test: np.ndarray,
        y_actual: np.ndarray
    ) -> Dict:
        """
        Test a specific model's accuracy
        
        Args:
            model_name: Name of model to test
            X_test: Test features
            y_actual: Actual speeds (ground truth)
        
        Returns:
            Dict with accuracy metrics
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing model: {model_name}")
            logger.info(f"{'='*60}")
            
            model = self.models[model_name]
            
            # Make predictions
            logger.info("Generating predictions...")
            y_pred = model.predict(X_test)
            
            # Calculate metrics
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            
            mae = mean_absolute_error(y_actual, y_pred)
            rmse = np.sqrt(mean_squared_error(y_actual, y_pred))
            r2 = r2_score(y_actual, y_pred)
            
            # Additional metrics
            mean_error = np.mean(y_pred - y_actual)
            median_error = np.median(np.abs(y_pred - y_actual))
            max_error = np.max(np.abs(y_pred - y_actual))
            
            # Prediction distribution
            pred_within_5mph = np.mean(np.abs(y_pred - y_actual) <= 5.0) * 100
            pred_within_10mph = np.mean(np.abs(y_pred - y_actual) <= 10.0) * 100
            
            # Assess quality
            mae_status = "✓ EXCELLENT" if mae < self.TARGET_MAE else ("⚠ ACCEPTABLE" if mae < self.WARNING_MAE else "✗ POOR")
            rmse_status = "✓ EXCELLENT" if rmse < self.TARGET_RMSE else ("⚠ ACCEPTABLE" if rmse < self.WARNING_RMSE else "✗ POOR")
            r2_status = "✓ EXCELLENT" if r2 > self.TARGET_R2 else ("⚠ ACCEPTABLE" if r2 > self.WARNING_R2 else "✗ POOR")
            
            results = {
                'model_name': model_name,
                'mae': mae,
                'rmse': rmse,
                'r2': r2,
                'mean_error': mean_error,
                'median_error': median_error,
                'max_error': max_error,
                'pred_within_5mph': pred_within_5mph,
                'pred_within_10mph': pred_within_10mph,
                'mae_status': mae_status,
                'rmse_status': rmse_status,
                'r2_status': r2_status,
                'n_samples': len(y_actual)
            }
            
            # Log results
            logger.info(f"\nAccuracy Metrics:")
            logger.info(f"  MAE:  {mae:.2f} mph {mae_status}")
            logger.info(f"  RMSE: {rmse:.2f} mph {rmse_status}")
            logger.info(f"  R²:   {r2:.3f} {r2_status}")
            logger.info(f"\nError Distribution:")
            logger.info(f"  Mean Error:   {mean_error:+.2f} mph")
            logger.info(f"  Median Error: {median_error:.2f} mph")
            logger.info(f"  Max Error:    {max_error:.2f} mph")
            logger.info(f"\nPrediction Accuracy:")
            logger.info(f"  Within 5 mph:  {pred_within_5mph:.1f}%")
            logger.info(f"  Within 10 mph: {pred_within_10mph:.1f}%")
            
            # Overall assessment
            overall_good = (mae < self.WARNING_MAE and rmse < self.WARNING_RMSE and r2 > self.WARNING_R2)
            overall_excellent = (mae < self.TARGET_MAE and rmse < self.TARGET_RMSE and r2 > self.TARGET_R2)
            
            if overall_excellent:
                logger.info(f"\n✓ OVERALL: EXCELLENT - Model is production-ready")
            elif overall_good:
                logger.info(f"\n⚠ OVERALL: ACCEPTABLE - Model usable but could be improved")
            else:
                logger.info(f"\n✗ OVERALL: POOR - Model needs retraining")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to test model {model_name}: {str(e)}", exc_info=True)
            return {}
    
    def run_comprehensive_test(self) -> Dict:
        """
        Run comprehensive ML model testing
        
        Returns:
            Dict with all test results
        """
        logger.info("\n" + "="*80)
        logger.info("SAFETY-CRITICAL: ML MODEL ACCURACY TESTING")
        logger.info("="*80)
        
        # Load models
        if not self.load_models_from_hdfs():
            logger.error("✗ Failed to load models from HDFS")
            return {'status': 'FAILED', 'error': 'Model loading failed'}
        
        # Load test data
        df_test = self.load_metr_la_test_data()
        if df_test.empty:
            logger.error("✗ No test data available")
            return {'status': 'FAILED', 'error': 'No test data'}
        
        # Prepare features
        X_test, y_actual = self.prepare_features(df_test)
        if len(X_test) == 0:
            logger.error("✗ Feature preparation failed")
            return {'status': 'FAILED', 'error': 'Feature preparation failed'}
        
        # Test each speed prediction model
        models_to_test = ['random_forest_speed', 'gradient_boosting_speed']
        
        all_results = {}
        for model_name in models_to_test:
            if model_name in self.models:
                results = self.test_model_accuracy(model_name, X_test, y_actual)
                all_results[model_name] = results
        
        # Generate summary
        summary = self._generate_summary(all_results)
        
        return {
            'status': 'SUCCESS',
            'timestamp': datetime.now().isoformat(),
            'test_data_samples': len(y_actual),
            'models_tested': list(all_results.keys()),
            'results': all_results,
            'summary': summary
        }
    
    def _generate_summary(self, results: Dict) -> Dict:
        """Generate test summary"""
        if not results:
            return {'overall_status': 'FAILED', 'message': 'No test results'}
        
        # Find best model
        best_model = min(results.keys(), key=lambda k: results[k].get('mae', float('inf')))
        best_mae = results[best_model]['mae']
        
        # Overall safety assessment
        all_acceptable = all(
            r['mae'] < self.WARNING_MAE and
            r['rmse'] < self.WARNING_RMSE and
            r['r2'] > self.WARNING_R2
            for r in results.values()
        )
        
        any_excellent = any(
            r['mae'] < self.TARGET_MAE and
            r['rmse'] < self.TARGET_RMSE and
            r['r2'] > self.TARGET_R2
            for r in results.values()
        )
        
        if any_excellent:
            status = "PRODUCTION_READY"
            message = "✓ At least one model meets excellence criteria"
        elif all_acceptable:
            status = "ACCEPTABLE"
            message = "⚠ Models acceptable but could be improved"
        else:
            status = "NEEDS_IMPROVEMENT"
            message = "✗ Models need retraining for production use"
        
        return {
            'overall_status': status,
            'message': message,
            'best_model': best_model,
            'best_mae': best_mae,
            'recommendation': self._get_recommendation(status, best_mae)
        }
    
    def _get_recommendation(self, status: str, mae: float) -> str:
        """Get recommendation based on test results"""
        if status == "PRODUCTION_READY":
            return (
                "Models are accurate enough for production deployment. "
                "Continue with end-to-end testing and monitoring setup."
            )
        elif status == "ACCEPTABLE":
            return (
                f"Models usable (MAE={mae:.1f} mph) but accuracy could be improved. "
                "Consider: 1) More training data, 2) Feature engineering, "
                "3) Hyperparameter tuning. Safe to continue testing."
            )
        else:
            return (
                f"Models not accurate enough (MAE={mae:.1f} mph > {self.WARNING_MAE} target). "
                "DO NOT DEPLOY TO PRODUCTION. Retrain models with: "
                "1) More diverse training data, 2) Better feature engineering, "
                "3) Different algorithms, 4) Ensemble methods."
            )


def main():
    """Run ML model accuracy testing"""
    tester = MLModelTester()
    results = tester.run_comprehensive_test()
    
    # Save results
    output_dir = Path("./test_results")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"ml_accuracy_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\n✓ Test results saved to: {output_file}")
    
    # Print final summary
    if results['status'] == 'SUCCESS':
        summary = results['summary']
        logger.info(f"\n{'='*80}")
        logger.info("FINAL ASSESSMENT")
        logger.info(f"{'='*80}")
        logger.info(f"Status: {summary['overall_status']}")
        logger.info(f"Message: {summary['message']}")
        logger.info(f"Best Model: {summary['best_model']} (MAE={summary['best_mae']:.2f} mph)")
        logger.info(f"\nRecommendation:\n{summary['recommendation']}")
        logger.info(f"{'='*80}\n")
    
    return results


if __name__ == '__main__':
    main()
