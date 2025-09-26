"""
Comprehensive unit tests for ML training components

Tests all major ML training modules:
- Configuration management
- Data loading and preprocessing
- Model training
- Model evaluation  
- Model persistence
- Complete pipeline integration
"""

import unittest
import tempfile
import shutil
import os
import json
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from pathlib import Path

# Mock external dependencies
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ml'))

# Mock pyspark and sklearn imports for testing
mock_spark = MagicMock()
sys.modules['pyspark'] = mock_spark
sys.modules['pyspark.sql'] = mock_spark.sql
sys.modules['pyspark.sql.functions'] = mock_spark.sql.functions
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.ensemble'] = MagicMock()
sys.modules['sklearn.linear_model'] = MagicMock()
sys.modules['sklearn.metrics'] = MagicMock()
sys.modules['sklearn.model_selection'] = MagicMock()
sys.modules['sklearn.preprocessing'] = MagicMock()
sys.modules['xgboost'] = MagicMock()
sys.modules['lightgbm'] = MagicMock()
sys.modules['matplotlib'] = MagicMock()
sys.modules['seaborn'] = MagicMock()

# Import our modules
from config_manager import MLTrainingConfigManager
from data_loader import DataLoader
from model_trainer import ModelTrainer, TrainedModel
from model_evaluator import ModelEvaluator
from model_persistence import ModelPersistenceManager


class TestMLTrainingConfig(unittest.TestCase):
    """Test ML training configuration management"""
    
    def setUp(self):
        """Set up test configuration"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        
        # Create test configuration
        self.test_config = {
            "data": {
                "source": "hdfs://test/features",
                "format": "parquet",
                "train_ratio": 0.7,
                "val_ratio": 0.2,
                "test_ratio": 0.1
            },
            "models": {
                "linear_regression": {
                    "enabled": True,
                    "hyperparameters": {"fit_intercept": True}
                },
                "random_forest": {
                    "enabled": True,
                    "hyperparameters": {"n_estimators": 100}
                }
            },
            "training": {
                "primary_metric": "rmse",
                "cross_validation": {"enabled": True, "folds": 5}
            },
            "evaluation": {
                "metrics": ["rmse", "mae", "r2"],
                "generate_plots": True
            },
            "persistence": {
                "save_models": True,
                "versioning_strategy": "semantic"
            },
            "spark": {
                "app_name": "TestMLPipeline",
                "config": {"spark.executor.memory": "2g"}
            },
            "logging": {
                "level": "INFO",
                "log_file_path": "test.log",
                "log_format": "%(asctime)s - %(levelname)s - %(message)s"
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
    
    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)
    
    def test_config_loading(self):
        """Test configuration loading"""
        config_manager = MLTrainingConfigManager(self.config_path)
        
        # Test basic loading
        self.assertEqual(config_manager.data_source.source, "hdfs://test/features")
        self.assertEqual(config_manager.data_source.train_ratio, 0.7)
        self.assertEqual(config_manager.training.primary_metric, "rmse")
        
        # Test model configurations
        enabled_models = config_manager.get_enabled_models()
        self.assertIn("linear_regression", enabled_models)
        self.assertIn("random_forest", enabled_models)
        
        # Test Spark configuration
        self.assertEqual(config_manager.spark_config.app_name, "TestMLPipeline")
    
    def test_config_validation(self):
        """Test configuration validation"""
        # Test invalid ratio sum
        invalid_config = self.test_config.copy()
        invalid_config["data"]["train_ratio"] = 0.8
        invalid_config["data"]["val_ratio"] = 0.3
        
        invalid_config_path = os.path.join(self.temp_dir, "invalid_config.json")
        with open(invalid_config_path, 'w') as f:
            json.dump(invalid_config, f)
        
        with self.assertRaises(ValueError):
            MLTrainingConfigManager(invalid_config_path)


class TestDataLoader(unittest.TestCase):
    """Test data loading and preprocessing"""
    
    def setUp(self):
        """Set up test data and configuration"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock configuration
        self.mock_config = Mock()
        self.mock_config.data_source.source = "test://data"
        self.mock_config.data_source.format = "parquet"
        self.mock_config.data_source.train_ratio = 0.7
        self.mock_config.data_source.val_ratio = 0.2
        self.mock_config.data_source.test_ratio = 0.1
        self.mock_config.preprocessing.handle_missing_values = True
        self.mock_config.preprocessing.remove_outliers = True
        self.mock_config.preprocessing.normalize_features = True
        
        # Mock Spark session
        self.mock_spark = Mock()
        
        # Create test DataFrame
        np.random.seed(42)
        self.test_data = pd.DataFrame({
            'feature_1': np.random.normal(0, 1, 1000),
            'feature_2': np.random.normal(10, 2, 1000),
            'feature_3': np.random.exponential(1, 1000),
            'target': np.random.normal(5, 1, 1000)
        })
        
        # Add some missing values and outliers
        self.test_data.loc[np.random.choice(1000, 50), 'feature_1'] = np.nan
        self.test_data.loc[np.random.choice(1000, 10), 'feature_2'] = 100  # outliers
    
    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)
    
    @patch('data_loader.SparkSession')
    def test_data_loading(self, mock_spark_session):
        """Test basic data loading functionality"""
        # Mock Spark DataFrame
        mock_spark_df = Mock()
        mock_spark_df.toPandas.return_value = self.test_data
        self.mock_spark.read.parquet.return_value = mock_spark_df
        
        data_loader = DataLoader(self.mock_config, self.mock_spark)
        
        # Test loading
        with patch.object(data_loader, '_load_spark_dataframe', return_value=mock_spark_df):
            result = data_loader.load_data_complete_pipeline(convert_to_pandas=True)
        
        self.assertIn('pandas_dataframes', result)
        self.assertIn('train', result['pandas_dataframes'])
        self.assertIn('validation', result['pandas_dataframes'])
        self.assertIn('test', result['pandas_dataframes'])
    
    def test_data_splitting(self):
        """Test data splitting functionality"""
        data_loader = DataLoader(self.mock_config, self.mock_spark)
        
        train_data, val_data, test_data = data_loader._split_data_time_based(
            self.test_data, 0.7, 0.2, 0.1
        )
        
        # Check split sizes
        total_size = len(self.test_data)
        self.assertAlmostEqual(len(train_data) / total_size, 0.7, places=1)
        self.assertAlmostEqual(len(val_data) / total_size, 0.2, places=1)
        self.assertAlmostEqual(len(test_data) / total_size, 0.1, places=1)
        
        # Check no overlap
        train_indices = set(train_data.index)
        val_indices = set(val_data.index)
        test_indices = set(test_data.index)
        
        self.assertEqual(len(train_indices & val_indices), 0)
        self.assertEqual(len(train_indices & test_indices), 0)
        self.assertEqual(len(val_indices & test_indices), 0)
    
    def test_preprocessing(self):
        """Test data preprocessing"""
        data_loader = DataLoader(self.mock_config, self.mock_spark)
        
        # Test missing value handling
        processed_data = data_loader._handle_missing_values(self.test_data.copy())
        self.assertEqual(processed_data.isnull().sum().sum(), 0)
        
        # Test outlier removal
        processed_data = data_loader._remove_outliers(processed_data, ['feature_2'])
        self.assertTrue(processed_data['feature_2'].max() < 50)  # Outliers removed
        
        # Test normalization
        processed_data = data_loader._normalize_features(processed_data, ['feature_1', 'feature_2'])
        self.assertAlmostEqual(processed_data['feature_1'].mean(), 0, places=1)
        self.assertAlmostEqual(processed_data['feature_1'].std(), 1, places=1)


class TestModelTrainer(unittest.TestCase):
    """Test model training functionality"""
    
    def setUp(self):
        """Set up test configuration and data"""
        # Mock configuration
        self.mock_config = Mock()
        self.mock_config.get_enabled_models.return_value = {
            "linear_regression": Mock(hyperparameters={"fit_intercept": True}),
            "random_forest": Mock(hyperparameters={"n_estimators": 100})
        }
        self.mock_config.training.primary_metric = "rmse"
        self.mock_config.training.cross_validation.enabled = True
        self.mock_config.training.cross_validation.folds = 5
        self.mock_config.model_selection.ensemble_models = True
        
        # Create test data
        np.random.seed(42)
        self.X_train = pd.DataFrame({
            'feature_1': np.random.normal(0, 1, 100),
            'feature_2': np.random.normal(0, 1, 100)
        })
        self.y_train = pd.Series(np.random.normal(0, 1, 100))
        self.X_val = pd.DataFrame({
            'feature_1': np.random.normal(0, 1, 30),
            'feature_2': np.random.normal(0, 1, 30)
        })
        self.y_val = pd.Series(np.random.normal(0, 1, 30))
    
    @patch('model_trainer.ModelFactory')
    def test_model_training(self, mock_model_factory):
        """Test basic model training"""
        # Mock sklearn models
        mock_lr_model = Mock()
        mock_lr_model.fit.return_value = mock_lr_model
        mock_lr_model.predict.return_value = np.random.normal(0, 1, 30)
        
        mock_rf_model = Mock()
        mock_rf_model.fit.return_value = mock_rf_model
        mock_rf_model.predict.return_value = np.random.normal(0, 1, 30)
        
        mock_model_factory.create_model.side_effect = [mock_lr_model, mock_rf_model]
        
        trainer = ModelTrainer(self.mock_config)
        
        # Mock metrics calculation
        with patch.object(trainer, '_calculate_metrics', return_value={'rmse': 1.0, 'mae': 0.8}):
            trained_models = trainer.train_all_models(
                self.X_train, self.y_train, self.X_val, self.y_val
            )
        
        self.assertEqual(len(trained_models), 2)
        self.assertIn("linear_regression", trained_models)
        self.assertIn("random_forest", trained_models)
    
    def test_model_selection(self):
        """Test best model selection"""
        trainer = ModelTrainer(self.mock_config)
        
        # Create mock trained models with different metrics
        mock_model_1 = Mock()
        mock_model_1.metrics.get_metric.return_value = 1.5  # Higher RMSE (worse)
        
        mock_model_2 = Mock()
        mock_model_2.metrics.get_metric.return_value = 1.0  # Lower RMSE (better)
        
        trained_models = {
            "model_1": mock_model_1,
            "model_2": mock_model_2
        }
        
        best_name, best_model = trainer.select_best_model(trained_models)
        self.assertEqual(best_name, "model_2")
        self.assertEqual(best_model, mock_model_2)


class TestModelEvaluator(unittest.TestCase):
    """Test model evaluation functionality"""
    
    def setUp(self):
        """Set up test configuration and data"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock configuration
        self.mock_config = Mock()
        self.mock_config.evaluation.metrics = ["rmse", "mae", "r2"]
        self.mock_config.evaluation.generate_plots = True
        self.mock_config.evaluation.residual_analysis = True
        
        # Create test data
        np.random.seed(42)
        self.X_test = pd.DataFrame({
            'feature_1': np.random.normal(0, 1, 50),
            'feature_2': np.random.normal(0, 1, 50)
        })
        self.y_test = pd.Series(np.random.normal(0, 1, 50))
        self.y_pred = pd.Series(np.random.normal(0, 1, 50))
    
    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)
    
    @patch('model_evaluator.plt')
    def test_model_evaluation(self, mock_plt):
        """Test model evaluation with metrics and plots"""
        evaluator = ModelEvaluator(self.mock_config)
        
        # Mock trained model
        mock_model = Mock()
        mock_model.predict.return_value = self.y_pred.values
        mock_model.model_name = "test_model"
        
        trained_models = {"test_model": mock_model}
        
        # Test evaluation
        results = evaluator.evaluate_all_models(
            trained_models, self.X_test, self.y_test, self.temp_dir
        )
        
        self.assertIn("test_model", results)
        self.assertIn("metrics", results["test_model"])
        
        # Check that plots were attempted to be generated
        self.assertTrue(mock_plt.figure.called)
    
    def test_metrics_calculation(self):
        """Test metrics calculation"""
        evaluator = ModelEvaluator(self.mock_config)
        
        # Test with known values
        y_true = np.array([1, 2, 3, 4, 5])
        y_pred = np.array([1.1, 2.1, 2.9, 3.8, 5.2])
        
        with patch('model_evaluator.mean_squared_error', return_value=0.04):
            with patch('model_evaluator.mean_absolute_error', return_value=0.16):
                with patch('model_evaluator.r2_score', return_value=0.96):
                    metrics = evaluator._calculate_comprehensive_metrics(y_true, y_pred)
        
        self.assertIn("rmse", metrics)
        self.assertIn("mae", metrics)
        self.assertIn("r2", metrics)


class TestModelPersistence(unittest.TestCase):
    """Test model persistence and versioning"""
    
    def setUp(self):
        """Set up test configuration and temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock configuration
        self.mock_config = Mock()
        self.mock_config.persistence.save_models = True
        self.mock_config.persistence.versioning_strategy = "semantic"
        self.mock_config.persistence.model_registry_path = self.temp_dir
        self.mock_config.persistence.hdfs_model_path = "hdfs://test/models"
        
        # Mock Spark session
        self.mock_spark = Mock()
    
    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)
    
    def test_model_saving(self):
        """Test model saving and versioning"""
        persistence_manager = ModelPersistenceManager(self.mock_config, self.mock_spark)
        
        # Mock trained model
        mock_trained_model = Mock()
        mock_trained_model.model_name = "test_model"
        mock_trained_model.model_type = "linear_regression"
        mock_trained_model.model = Mock()  # sklearn model
        mock_trained_model.metrics.to_dict.return_value = {"rmse": 1.0, "mae": 0.8}
        
        # Test saving
        with patch.object(persistence_manager, '_save_model_to_hdfs'):
            version_id = persistence_manager.save_trained_model(
                trained_model=mock_trained_model,
                feature_columns=["feature_1", "feature_2"],
                target_columns=["target"],
                data_schema={"total_features": 2},
                description="Test model",
                tags=["test"],
                created_by="unittest"
            )
        
        self.assertIsNotNone(version_id)
        self.assertTrue(version_id.startswith("test_model"))
    
    def test_model_loading(self):
        """Test model loading"""
        persistence_manager = ModelPersistenceManager(self.mock_config, self.mock_spark)
        
        # Mock model loading
        mock_model = Mock()
        mock_metadata = {"model_name": "test_model", "version": "1.0.0"}
        
        with patch.object(persistence_manager, '_load_model_from_hdfs', return_value=(mock_model, mock_metadata)):
            loaded_model, metadata = persistence_manager.load_model("test_model", "1.0.0")
        
        self.assertEqual(loaded_model, mock_model)
        self.assertEqual(metadata["model_name"], "test_model")
    
    def test_versioning(self):
        """Test model versioning system"""
        persistence_manager = ModelPersistenceManager(self.mock_config, self.mock_spark)
        version_manager = persistence_manager.version_manager
        
        # Test semantic versioning
        version1 = version_manager.generate_new_version("test_model", "semantic")
        self.assertEqual(version1, "1.0.0")
        
        # Add version to registry
        version_manager.model_versions["test_model"] = ["1.0.0"]
        
        version2 = version_manager.generate_new_version("test_model", "semantic", version_type="minor")
        self.assertEqual(version2, "1.1.0")


class TestMLTrainingPipelineIntegration(unittest.TestCase):
    """Integration tests for complete ML training pipeline"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "integration_config.json")
        
        # Create minimal test configuration
        test_config = {
            "data": {
                "source": "test://features",
                "format": "parquet",
                "train_ratio": 0.7,
                "val_ratio": 0.2,
                "test_ratio": 0.1
            },
            "models": {
                "linear_regression": {
                    "enabled": True,
                    "hyperparameters": {"fit_intercept": True},
                    "hyperparameter_tuning": False
                }
            },
            "training": {
                "primary_metric": "rmse",
                "cross_validation": {"enabled": False, "folds": 5}
            },
            "evaluation": {
                "metrics": ["rmse", "mae"],
                "generate_plots": False
            },
            "persistence": {
                "save_models": True,
                "versioning_strategy": "semantic",
                "model_registry_path": self.temp_dir
            },
            "spark": {
                "app_name": "IntegrationTest",
                "config": {}
            },
            "logging": {
                "level": "ERROR",
                "log_file_path": os.path.join(self.temp_dir, "test.log"),
                "log_format": "%(message)s"
            },
            "preprocessing": {
                "handle_missing_values": True,
                "remove_outliers": False,
                "normalize_features": False
            },
            "model_selection": {
                "ensemble_models": False
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
    
    def tearDown(self):
        """Clean up integration test files"""
        shutil.rmtree(self.temp_dir)
    
    @patch('ml_training_pipeline.SparkSession')
    def test_pipeline_initialization(self, mock_spark_session):
        """Test pipeline initialization"""
        from ml_training_pipeline import MLTrainingPipeline
        
        mock_spark = Mock()
        mock_spark_session.builder.appName.return_value.getOrCreate.return_value = mock_spark
        
        pipeline = MLTrainingPipeline(self.config_path, mock_spark)
        
        self.assertIsNotNone(pipeline.config)
        self.assertIsNotNone(pipeline.data_loader)
        self.assertIsNotNone(pipeline.model_trainer)
        self.assertIsNotNone(pipeline.model_evaluator)
        self.assertIsNotNone(pipeline.model_persistence)


def create_test_suite():
    """Create comprehensive test suite"""
    suite = unittest.TestSuite()
    
    # Add all test cases
    test_cases = [
        TestMLTrainingConfig,
        TestDataLoader,
        TestModelTrainer,
        TestModelEvaluator,
        TestModelPersistence,
        TestMLTrainingPipelineIntegration
    ]
    
    for test_case in test_cases:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_case)
        suite.addTests(tests)
    
    return suite


def run_tests(verbosity=2):
    """Run all tests with specified verbosity"""
    suite = create_test_suite()
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Run tests
    success = run_tests(verbosity=2)
    
    if success:
        print("\n" + "="*60)
        print("ALL ML TRAINING TESTS PASSED")
        print("="*60)
        exit(0)
    else:
        print("\n" + "="*60)
        print("SOME ML TRAINING TESTS FAILED")
        print("="*60)
        exit(1)