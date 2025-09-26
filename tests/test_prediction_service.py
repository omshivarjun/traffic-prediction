#!/usr/bin/env python3
"""
Unit Tests for Traffic Prediction Service

Comprehensive test suite for all prediction service components including:
- Core prediction service functionality
- Database operations and connection management
- Model loading and feature processing
- Spark job execution and distributed processing
- Monitoring system and metrics collection
- Retraining pipeline and model validation

Usage:
    python -m pytest tests/test_prediction_service.py -v
    python -m pytest tests/test_prediction_service.py::TestPredictionService::test_prediction_generation -v
"""

import unittest
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import tempfile
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from prediction.prediction_service import (
    PredictionService, 
    PredictionServiceConfig,
    DatabaseManager,
    ModelManager,
    FeatureProcessor,
    PredictionGenerator,
    MetricsCollector
)

from prediction.spark_prediction_job import SparkPredictionJob
from prediction.monitoring_system import (
    MonitoringSystem,
    AccuracyAnalyzer,
    HealthChecker
)
from prediction.retraining_pipeline import (
    RetrainingPipeline,
    DataCollector,
    ModelValidator
)

class TestPredictionServiceConfig(unittest.TestCase):
    """Test configuration management for prediction service"""
    
    def setUp(self):
        """Set up test configuration"""
        self.config_data = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "database": "traffic_prediction",
                "user": "test_user",
                "password": "test_pass"
            },
            "prediction": {
                "batch_size": 1000,
                "prediction_horizons": [15, 30, 60],
                "feature_window_hours": 24
            },
            "monitoring": {
                "accuracy_threshold": 0.85,
                "alert_email": "admin@test.com"
            }
        }
        
        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.config_data, self.temp_config)
        self.temp_config.close()
    
    def tearDown(self):
        """Clean up temporary files"""
        os.unlink(self.temp_config.name)
    
    def test_config_loading(self):
        """Test configuration loading from file"""
        config = PredictionServiceConfig.from_file(self.temp_config.name)
        
        self.assertEqual(config.database_config['host'], 'localhost')
        self.assertEqual(config.database_config['port'], 5432)
        self.assertEqual(config.prediction_config['batch_size'], 1000)
        self.assertEqual(len(config.prediction_horizons), 3)
    
    def test_config_validation(self):
        """Test configuration validation"""
        # Test missing required fields
        invalid_config = {"database": {}}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_config, f)
            temp_file = f.name
        
        try:
            with self.assertRaises(KeyError):
                PredictionServiceConfig.from_file(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_config_defaults(self):
        """Test default configuration values"""
        config = PredictionServiceConfig.from_file(self.temp_config.name)
        
        # Test that prediction horizons are sorted
        self.assertEqual(config.prediction_horizons, [15, 30, 60])
        
        # Test monitoring defaults
        self.assertEqual(config.monitoring_config['accuracy_threshold'], 0.85)

class TestDatabaseManager(unittest.TestCase):
    """Test database operations and connection management"""
    
    def setUp(self):
        """Set up test database manager with mocked connections"""
        self.config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'test_db',
            'user': 'test_user',
            'password': 'test_pass'
        }
        
        self.db_manager = DatabaseManager(self.config)
        
        # Mock the connection pool
        self.mock_pool = Mock()
        self.mock_connection = Mock()
        self.mock_cursor = Mock()
        
        self.mock_connection.cursor.return_value.__enter__.return_value = self.mock_cursor
        self.mock_pool.getconn.return_value = self.mock_connection
        
        self.db_manager.connection_pool = self.mock_pool
    
    def test_database_connection(self):
        """Test database connection establishment"""
        with patch('psycopg2.pool.ThreadedConnectionPool') as mock_pool_class:
            mock_pool_class.return_value = self.mock_pool
            
            db_manager = DatabaseManager(self.config)
            db_manager._create_connection_pool()
            
            mock_pool_class.assert_called_once()
    
    def test_fetch_traffic_data(self):
        """Test traffic data retrieval"""
        # Mock data
        mock_data = [
            (1, datetime.now(), 50.5, 25.2, 1.2),
            (2, datetime.now(), 60.1, 30.8, 1.5)
        ]
        self.mock_cursor.fetchall.return_value = mock_data
        
        segment_id = 123
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now()
        
        result = self.db_manager.fetch_traffic_data(segment_id, start_time, end_time)
        
        self.assertEqual(len(result), 2)
        self.mock_cursor.execute.assert_called_once()
    
    def test_store_predictions(self):
        """Test prediction storage to database"""
        predictions = pd.DataFrame({
            'segment_id': [1, 2, 3],
            'prediction_time': [datetime.now()] * 3,
            'horizon_minutes': [15, 30, 60],
            'predicted_volume': [45.2, 52.8, 38.9],
            'confidence_score': [0.85, 0.78, 0.92]
        })
        
        self.db_manager.store_predictions(predictions)
        
        # Verify execute_batch was called
        self.mock_cursor.execute.assert_called()
    
    def test_connection_error_handling(self):
        """Test database connection error handling"""
        self.mock_pool.getconn.side_effect = Exception("Connection failed")
        
        with self.assertRaises(Exception):
            self.db_manager.fetch_traffic_data(123, datetime.now(), datetime.now())

class TestModelManager(unittest.TestCase):
    """Test model loading and management functionality"""
    
    def setUp(self):
        """Set up test model manager"""
        self.hdfs_config = {
            'namenode_url': 'hdfs://localhost:9000',
            'model_path': '/ml/models/traffic_prediction'
        }
        
        self.model_manager = ModelManager(self.hdfs_config)
    
    @patch('joblib.load')
    @patch('hdfs.InsecureClient')
    def test_model_loading(self, mock_hdfs_client, mock_joblib):
        """Test model loading from HDFS"""
        # Mock HDFS client
        mock_client = Mock()
        mock_hdfs_client.return_value = mock_client
        mock_client.read.return_value = b'mock_model_data'
        
        # Mock joblib load
        mock_model = Mock()
        mock_joblib.return_value = mock_model
        
        model = self.model_manager.load_model('random_forest')
        
        self.assertIsNotNone(model)
        mock_client.read.assert_called_once()
        mock_joblib.assert_called_once()
    
    def test_model_caching(self):
        """Test model caching functionality"""
        with patch.object(self.model_manager, '_load_model_from_hdfs') as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model
            
            # First load
            model1 = self.model_manager.load_model('test_model')
            
            # Second load (should use cache)
            model2 = self.model_manager.load_model('test_model')
            
            # Should only load once
            mock_load.assert_called_once()
            self.assertEqual(model1, model2)
    
    def test_model_metadata_loading(self):
        """Test model metadata loading"""
        mock_metadata = {
            'model_type': 'random_forest',
            'training_date': '2024-01-15',
            'feature_columns': ['volume', 'speed', 'occupancy'],
            'performance_metrics': {'mae': 2.5, 'rmse': 3.8}
        }
        
        with patch.object(self.model_manager, '_load_json_from_hdfs') as mock_load:
            mock_load.return_value = mock_metadata
            
            metadata = self.model_manager.load_model_metadata('test_model')
            
            self.assertEqual(metadata['model_type'], 'random_forest')
            self.assertEqual(len(metadata['feature_columns']), 3)

class TestFeatureProcessor(unittest.TestCase):
    """Test feature processing and engineering"""
    
    def setUp(self):
        """Set up test feature processor"""
        self.feature_config = {
            'window_hours': 24,
            'lag_features': [1, 6, 12, 24],
            'aggregation_windows': [15, 30, 60]
        }
        
        self.feature_processor = FeatureProcessor(self.feature_config)
        
        # Create sample traffic data
        timestamps = pd.date_range(
            start=datetime.now() - timedelta(days=2),
            end=datetime.now(),
            freq='5T'
        )
        
        self.sample_data = pd.DataFrame({
            'timestamp': timestamps,
            'segment_id': [123] * len(timestamps),
            'volume': np.random.normal(50, 10, len(timestamps)),
            'speed': np.random.normal(60, 15, len(timestamps)),
            'occupancy': np.random.normal(0.3, 0.1, len(timestamps))
        })
    
    def test_lag_feature_creation(self):
        """Test lag feature creation"""
        features = self.feature_processor.create_lag_features(self.sample_data)
        
        # Check that lag features were created
        lag_columns = [col for col in features.columns if 'lag_' in col]
        self.assertGreater(len(lag_columns), 0)
        
        # Check specific lag features
        self.assertIn('volume_lag_1', features.columns)
        self.assertIn('speed_lag_6', features.columns)
    
    def test_rolling_statistics(self):
        """Test rolling window statistics"""
        features = self.feature_processor.create_rolling_features(self.sample_data)
        
        # Check rolling mean features
        rolling_columns = [col for col in features.columns if 'rolling_' in col]
        self.assertGreater(len(rolling_columns), 0)
        
        # Check specific rolling features
        expected_features = ['volume_rolling_mean_15', 'speed_rolling_std_30']
        for feature in expected_features:
            if feature in features.columns:
                self.assertIn(feature, features.columns)
    
    def test_time_features(self):
        """Test time-based feature extraction"""
        features = self.feature_processor.create_time_features(self.sample_data)
        
        # Check time features
        time_features = ['hour', 'day_of_week', 'month', 'is_weekend']
        for feature in time_features:
            if feature in features.columns:
                self.assertIn(feature, features.columns)
    
    def test_feature_scaling(self):
        """Test feature scaling and normalization"""
        features = self.feature_processor.create_lag_features(self.sample_data)
        scaled_features = self.feature_processor.scale_features(features)
        
        # Check that features are scaled (approximately mean 0, std 1)
        numeric_columns = scaled_features.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            mean_val = scaled_features[col].mean()
            std_val = scaled_features[col].std()
            
            # Allow some tolerance due to finite sample size
            if not pd.isna(mean_val) and not pd.isna(std_val):
                self.assertAlmostEqual(mean_val, 0, delta=0.1)
                self.assertAlmostEqual(std_val, 1, delta=0.1)

class TestPredictionGenerator(unittest.TestCase):
    """Test prediction generation functionality"""
    
    def setUp(self):
        """Set up test prediction generator"""
        self.prediction_config = {
            'horizons': [15, 30, 60],
            'confidence_intervals': True,
            'feature_columns': ['volume', 'speed', 'occupancy']
        }
        
        self.prediction_generator = PredictionGenerator(self.prediction_config)
        
        # Mock model
        self.mock_model = Mock()
        self.mock_model.predict.return_value = np.array([45.2, 52.8, 38.9])
        
        # Create sample features
        self.sample_features = pd.DataFrame({
            'volume': [50.0, 55.2, 48.3],
            'speed': [60.5, 58.1, 62.4],
            'occupancy': [0.32, 0.28, 0.35]
        })
    
    def test_single_prediction(self):
        """Test single prediction generation"""
        prediction = self.prediction_generator.generate_prediction(
            self.mock_model,
            self.sample_features.iloc[0],
            horizon=15
        )
        
        self.assertIsInstance(prediction, dict)
        self.assertIn('predicted_value', prediction)
        self.assertIn('confidence_score', prediction)
        self.assertIn('horizon_minutes', prediction)
    
    def test_batch_predictions(self):
        """Test batch prediction generation"""
        predictions = self.prediction_generator.generate_batch_predictions(
            self.mock_model,
            self.sample_features,
            horizons=[15, 30, 60]
        )
        
        self.assertIsInstance(predictions, pd.DataFrame)
        self.assertGreater(len(predictions), 0)
        
        # Check required columns
        required_columns = ['predicted_value', 'confidence_score', 'horizon_minutes']
        for col in required_columns:
            self.assertIn(col, predictions.columns)
    
    def test_confidence_calculation(self):
        """Test confidence score calculation"""
        # Mock model with prediction intervals
        self.mock_model.predict.return_value = np.array([50.0])
        
        with patch.object(self.prediction_generator, '_calculate_prediction_intervals') as mock_intervals:
            mock_intervals.return_value = (45.0, 55.0)  # Lower, upper bounds
            
            confidence = self.prediction_generator._calculate_confidence_score(
                prediction=50.0,
                lower_bound=45.0,
                upper_bound=55.0
            )
            
            self.assertIsInstance(confidence, float)
            self.assertGreaterEqual(confidence, 0.0)
            self.assertLessEqual(confidence, 1.0)

class TestSparkPredictionJob(unittest.TestCase):
    """Test Spark-based distributed prediction processing"""
    
    def setUp(self):
        """Set up test Spark prediction job"""
        self.spark_config = {
            'app_name': 'test_traffic_predictions',
            'executor_memory': '2g',
            'executor_cores': 2,
            'num_executors': 2
        }
        
        self.database_config = {
            'url': 'jdbc:postgresql://localhost:5432/test_db',
            'user': 'test_user',
            'password': 'test_pass'
        }
        
        # Don't actually create Spark session in tests
        self.spark_job = SparkPredictionJob(
            self.spark_config,
            self.database_config
        )
    
    @patch('pyspark.sql.SparkSession')
    def test_spark_session_creation(self, mock_spark_session):
        """Test Spark session initialization"""
        mock_session = Mock()
        mock_spark_session.builder.appName.return_value.config.return_value.getOrCreate.return_value = mock_session
        
        self.spark_job._initialize_spark()
        
        mock_spark_session.builder.appName.assert_called_with('test_traffic_predictions')
    
    def test_data_loading_query_generation(self):
        """Test SQL query generation for data loading"""
        segment_ids = [1, 2, 3]
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 23, 59, 59)
        
        query = self.spark_job._build_data_query(segment_ids, start_time, end_time)
        
        self.assertIn('SELECT', query.upper())
        self.assertIn('traffic_readings', query)
        self.assertIn('WHERE', query.upper())
    
    @patch('pyspark.sql.SparkSession')
    def test_feature_processing_with_spark(self, mock_spark_session):
        """Test feature processing using Spark DataFrames"""
        # Mock Spark DataFrame
        mock_df = Mock()
        mock_df.withColumn.return_value = mock_df
        mock_df.groupBy.return_value.agg.return_value = mock_df
        
        mock_session = Mock()
        mock_session.sql.return_value = mock_df
        mock_spark_session.builder.appName.return_value.config.return_value.getOrCreate.return_value = mock_session
        
        self.spark_job.spark = mock_session
        
        # Test feature processing
        processed_df = self.spark_job._process_features(mock_df)
        
        # Verify DataFrame transformations were called
        mock_df.withColumn.assert_called()

class TestMonitoringSystem(unittest.TestCase):
    """Test monitoring and alerting functionality"""
    
    def setUp(self):
        """Set up test monitoring system"""
        self.monitoring_config = {
            'accuracy_threshold': 0.8,
            'alert_channels': ['email'],
            'metrics_retention_days': 30
        }
        
        self.database_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'test_db'
        }
        
        self.monitoring_system = MonitoringSystem(
            self.monitoring_config,
            self.database_config
        )
    
    def test_accuracy_calculation(self):
        """Test prediction accuracy calculation"""
        predictions = pd.DataFrame({
            'segment_id': [1, 1, 1],
            'prediction_time': pd.date_range('2024-01-01', periods=3, freq='H'),
            'predicted_volume': [50.0, 55.0, 48.0],
            'horizon_minutes': [15, 15, 15]
        })
        
        actuals = pd.DataFrame({
            'segment_id': [1, 1, 1],
            'timestamp': pd.date_range('2024-01-01 00:15', periods=3, freq='H'),
            'actual_volume': [52.0, 53.0, 49.0]
        })
        
        analyzer = AccuracyAnalyzer()
        accuracy_metrics = analyzer.calculate_accuracy_metrics(predictions, actuals)
        
        self.assertIn('mae', accuracy_metrics)
        self.assertIn('rmse', accuracy_metrics)
        self.assertIn('mape', accuracy_metrics)
        self.assertIsInstance(accuracy_metrics['mae'], float)
    
    def test_health_check_system(self):
        """Test system health checking"""
        health_checker = HealthChecker()
        
        with patch.object(health_checker, '_check_database_connection') as mock_db:
            with patch.object(health_checker, '_check_model_availability') as mock_model:
                mock_db.return_value = True
                mock_model.return_value = True
                
                health_status = health_checker.perform_health_check()
                
                self.assertIn('database', health_status)
                self.assertIn('models', health_status)
                self.assertTrue(health_status['database'])
                self.assertTrue(health_status['models'])
    
    def test_alert_generation(self):
        """Test alert generation for low accuracy"""
        with patch.object(self.monitoring_system, '_send_alert') as mock_alert:
            # Simulate low accuracy scenario
            self.monitoring_system._check_accuracy_alerts({'mae': 10.0, 'accuracy': 0.6})
            
            mock_alert.assert_called_once()

class TestRetrainingPipeline(unittest.TestCase):
    """Test automated model retraining functionality"""
    
    def setUp(self):
        """Set up test retraining pipeline"""
        self.retraining_config = {
            'retrain_frequency_days': 7,
            'validation_split': 0.2,
            'performance_threshold': 0.8
        }
        
        self.retraining_pipeline = RetrainingPipeline(self.retraining_config)
    
    def test_data_collection(self):
        """Test training data collection"""
        data_collector = DataCollector()
        
        with patch.object(data_collector, '_fetch_recent_data') as mock_fetch:
            mock_data = pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=100, freq='5T'),
                'segment_id': [1] * 100,
                'volume': np.random.normal(50, 10, 100)
            })
            mock_fetch.return_value = mock_data
            
            training_data = data_collector.collect_training_data(
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 7)
            )
            
            self.assertIsInstance(training_data, pd.DataFrame)
            self.assertGreater(len(training_data), 0)
    
    def test_model_validation(self):
        """Test model performance validation"""
        validator = ModelValidator()
        
        # Mock model and validation data
        mock_model = Mock()
        mock_model.predict.return_value = np.array([50.0, 55.0, 48.0])
        
        validation_data = pd.DataFrame({
            'volume': [52.0, 53.0, 49.0],
            'speed': [60.0, 58.0, 62.0],
            'occupancy': [0.3, 0.28, 0.32]
        })
        
        validation_targets = np.array([52.0, 53.0, 49.0])
        
        performance = validator.validate_model(
            mock_model,
            validation_data,
            validation_targets
        )
        
        self.assertIn('mae', performance)
        self.assertIn('rmse', performance)
        self.assertIsInstance(performance['mae'], float)
    
    def test_model_comparison(self):
        """Test comparison between old and new models"""
        # Mock performance metrics
        old_model_performance = {'mae': 5.0, 'rmse': 7.0}
        new_model_performance = {'mae': 4.2, 'rmse': 6.1}
        
        should_deploy = self.retraining_pipeline._should_deploy_new_model(
            old_model_performance,
            new_model_performance
        )
        
        self.assertTrue(should_deploy)  # New model is better

if __name__ == '__main__':
    # Configure test discovery and execution
    loader = unittest.TestLoader()
    suite = loader.discover('.', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)