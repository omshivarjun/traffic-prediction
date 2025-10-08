# Task 4: Phase 4 - ML Training Pipeline

## Overview
Implement machine learning training pipeline using Spark MLlib to train three prediction models: Linear Regression (baseline), Random Forest (primary - 99.96% R²), and Gradient Boosted Trees. Train on engineered features and persist models to HDFS.

**Status**: Not Started  
**Dependencies**: Task 3 (Feature Engineering must be complete)  
**Priority**: High

**Target Performance** (from workflow document):
- **Random Forest**: R² = 0.9996, RMSE = 0.752, MAE = 0.289, Model Size = 27.9 MB
- **Gradient Boosted Trees**: R² = 0.9992, RMSE = 1.061
- **Linear Regression**: Baseline comparison

**Most Important Feature**: `traffic_efficiency` = 81% feature importance

---

## Subtask 4.1: Data Loading and Preprocessing

**Status**: Not Started

### Description
Load engineered features from HDFS, prepare train/test splits, and apply feature scaling.

### Implementation Details

**Data Loading from HDFS**:
```python
# src/ml-training/data_loader.py
from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler, StandardScaler, OneHotEncoder
from pyspark.ml import Pipeline
import logging

logger = logging.getLogger(__name__)

class TrafficDataLoader:
    """Load and preprocess traffic features for ML training"""
    
    def __init__(self, spark):
        self.spark = spark
        
        # Define feature columns
        self.numeric_features = [
            # Time features
            "hour_sin", "hour_cos", "time_since_midnight",
            # Spatial features
            "lat_normalized", "lon_normalized", "distance_from_center",
            # Traffic features (traffic_efficiency = 81% importance!)
            "traffic_efficiency", "occupancy_ratio", "flow_rate",
            "speed_variance",
            # Historical features
            "speed_lag_1", "speed_lag_2", "speed_lag_3",
            "speed_ma_15min", "speed_ma_30min", "speed_ma_60min"
        ]
        
        self.categorical_features = [
            "highway_encoded",
            "is_weekend",
            "is_rush_hour",
            "sensor_cluster",
            "congestion_level"
        ]
        
        self.target_column = "speed"  # What we're predicting
    
    def load_features(self, hdfs_path, start_date=None, end_date=None):
        """
        Load features from HDFS with optional date filtering
        
        Args:
            hdfs_path: Path to ml-features in HDFS
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            
        Returns:
            DataFrame with features
        """
        logger.info(f"Loading features from {hdfs_path}")
        
        df = self.spark.read.parquet(hdfs_path)
        
        # Filter by date if specified
        if start_date or end_date:
            if start_date:
                df = df.filter(col("timestamp") >= start_date)
            if end_date:
                df = df.filter(col("timestamp") <= end_date)
        
        logger.info(f"Loaded {df.count()} records")
        
        return df
    
    def prepare_features(self, df):
        """
        Prepare features for ML training
        
        Steps:
        1. Handle categorical variables
        2. Assemble feature vector
        3. Apply standard scaling
        
        Args:
            df: DataFrame with raw features
            
        Returns:
            DataFrame with 'features' vector column
        """
        # One-hot encode categorical features
        encoders = []
        encoded_cols = []
        
        for cat_col in self.categorical_features:
            encoder = OneHotEncoder(
                inputCol=cat_col,
                outputCol=f"{cat_col}_encoded"
            )
            encoders.append(encoder)
            encoded_cols.append(f"{cat_col}_encoded")
        
        # Assemble all features into single vector
        all_features = self.numeric_features + encoded_cols
        
        assembler = VectorAssembler(
            inputCols=all_features,
            outputCol="raw_features"
        )
        
        # Apply standard scaling (important for linear models)
        scaler = StandardScaler(
            inputCol="raw_features",
            outputCol="features",
            withMean=True,
            withStd=True
        )
        
        # Create preprocessing pipeline
        preprocessing_pipeline = Pipeline(stages=encoders + [assembler, scaler])
        
        # Fit and transform
        logger.info("Fitting preprocessing pipeline...")
        model = preprocessing_pipeline.fit(df)
        
        logger.info("Transforming features...")
        df_transformed = model.transform(df)
        
        # Select only necessary columns
        df_final = df_transformed.select(
            "sensor_id",
            "timestamp",
            "features",
            col(self.target_column).alias("label")
        )
        
        return df_final, model
    
    def train_test_split(self, df, test_ratio=0.2, seed=42):
        """
        Split data into train and test sets
        
        Args:
            df: DataFrame to split
            test_ratio: Fraction for test set (default 0.2 = 80/20 split)
            seed: Random seed for reproducibility
            
        Returns:
            (train_df, test_df) tuple
        """
        train_df, test_df = df.randomSplit([1 - test_ratio, test_ratio], seed=seed)
        
        logger.info(f"Train set: {train_df.count()} records")
        logger.info(f"Test set: {test_df.count()} records")
        
        return train_df, test_df
```

### Validation Criteria
- [ ] All feature columns loaded correctly
- [ ] No null values in features
- [ ] Feature vector assembled (numeric + one-hot encoded)
- [ ] Standard scaling applied (mean=0, std=1)
- [ ] 80/20 train/test split achieved
- [ ] Target variable (speed) preserved

---

## Subtask 4.2: Linear Regression Baseline

**Status**: Not Started

### Description
Train simple Linear Regression model as baseline for comparison.

### Implementation Details

```python
# src/ml-training/models/linear_regression.py
from pyspark.ml.regression import LinearRegression
from pyspark.ml.evaluation import RegressionEvaluator
import logging

logger = logging.getLogger(__name__)

class LinearRegressionTrainer:
    """Train Linear Regression baseline model"""
    
    def __init__(self):
        self.model = None
        self.metrics = {}
    
    def train(self, train_df):
        """
        Train Linear Regression model
        
        Args:
            train_df: Training DataFrame with 'features' and 'label'
            
        Returns:
            Fitted model
        """
        logger.info("Training Linear Regression model...")
        
        lr = LinearRegression(
            featuresCol="features",
            labelCol="label",
            maxIter=100,
            regParam=0.01,  # L2 regularization
            elasticNetParam=0.0  # Pure L2 (Ridge regression)
        )
        
        self.model = lr.fit(train_df)
        
        # Training metrics
        training_summary = self.model.summary
        logger.info(f"Training RMSE: {training_summary.rootMeanSquaredError:.4f}")
        logger.info(f"Training R²: {training_summary.r2:.4f}")
        logger.info(f"Training MAE: {training_summary.meanAbsoluteError:.4f}")
        
        return self.model
    
    def evaluate(self, test_df):
        """
        Evaluate model on test set
        
        Args:
            test_df: Test DataFrame
            
        Returns:
            Dictionary of evaluation metrics
        """
        logger.info("Evaluating Linear Regression on test set...")
        
        predictions = self.model.transform(test_df)
        
        # Calculate metrics
        evaluator_rmse = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="rmse"
        )
        
        evaluator_r2 = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="r2"
        )
        
        evaluator_mae = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="mae"
        )
        
        self.metrics = {
            "rmse": evaluator_rmse.evaluate(predictions),
            "r2": evaluator_r2.evaluate(predictions),
            "mae": evaluator_mae.evaluate(predictions)
        }
        
        logger.info(f"Test RMSE: {self.metrics['rmse']:.4f}")
        logger.info(f"Test R²: {self.metrics['r2']:.4f}")
        logger.info(f"Test MAE: {self.metrics['mae']:.4f}")
        
        return self.metrics
```

### Expected Performance
- R² > 0.90 (baseline should be decent)
- RMSE < 5.0 mph
- MAE < 3.0 mph

---

## Subtask 4.3: Random Forest Model (Primary - 99.96% R²)

**Status**: Not Started

### Description
Train Random Forest model targeting 99.96% R² accuracy as specified in workflow document. This is the PRIMARY production model.

### Implementation Details

```python
# src/ml-training/models/random_forest.py
from pyspark.ml.regression import RandomForestRegressor
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
import logging

logger = logging.getLogger(__name__)

class RandomForestTrainer:
    """Train Random Forest regression model (PRIMARY MODEL)"""
    
    def __init__(self):
        self.model = None
        self.metrics = {}
        self.feature_importance = None
    
    def train(self, train_df, tune_hyperparameters=True):
        """
        Train Random Forest model
        
        Target Performance:
        - R² = 0.9996
        - RMSE = 0.752
        - MAE = 0.289
        - Model Size = 27.9 MB
        
        Args:
            train_df: Training DataFrame
            tune_hyperparameters: Whether to perform grid search
            
        Returns:
            Fitted model
        """
        logger.info("Training Random Forest model...")
        
        rf = RandomForestRegressor(
            featuresCol="features",
            labelCol="label",
            numTrees=100,  # Start with 100 trees
            maxDepth=10,
            minInstancesPerNode=1,
            seed=42
        )
        
        if tune_hyperparameters:
            logger.info("Performing hyperparameter tuning...")
            
            # Parameter grid
            param_grid = ParamGridBuilder() \
                .addGrid(rf.numTrees, [50, 100, 150]) \
                .addGrid(rf.maxDepth, [8, 10, 12]) \
                .addGrid(rf.minInstancesPerNode, [1, 2, 5]) \
                .build()
            
            # Cross-validator
            evaluator = RegressionEvaluator(
                labelCol="label",
                predictionCol="prediction",
                metricName="r2"
            )
            
            cv = CrossValidator(
                estimator=rf,
                estimatorParamMaps=param_grid,
                evaluator=evaluator,
                numFolds=5,
                seed=42
            )
            
            cv_model = cv.fit(train_df)
            self.model = cv_model.bestModel
            
            # Log best parameters
            logger.info(f"Best numTrees: {self.model.getNumTrees}")
            logger.info(f"Best maxDepth: {self.model.getMaxDepth()}")
            
        else:
            self.model = rf.fit(train_df)
        
        # Extract feature importance
        self.feature_importance = self.model.featureImportances
        logger.info("Feature importances extracted")
        
        return self.model
    
    def evaluate(self, test_df):
        """
        Evaluate Random Forest model
        
        Target: R² = 0.9996, RMSE = 0.752
        
        Args:
            test_df: Test DataFrame
            
        Returns:
            Dictionary of metrics
        """
        logger.info("Evaluating Random Forest on test set...")
        
        predictions = self.model.transform(test_df)
        
        # Calculate all metrics
        evaluator_rmse = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="rmse"
        )
        
        evaluator_r2 = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="r2"
        )
        
        evaluator_mae = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="mae"
        )
        
        self.metrics = {
            "rmse": evaluator_rmse.evaluate(predictions),
            "r2": evaluator_r2.evaluate(predictions),
            "mae": evaluator_mae.evaluate(predictions),
            "num_trees": self.model.getNumTrees,
            "max_depth": self.model.getMaxDepth()
        }
        
        logger.info(f"Test RMSE: {self.metrics['rmse']:.4f} (target: 0.752)")
        logger.info(f"Test R²: {self.metrics['r2']:.6f} (target: 0.9996)")
        logger.info(f"Test MAE: {self.metrics['mae']:.4f} (target: 0.289)")
        
        # Check if we met targets
        if self.metrics['r2'] >= 0.9996:
            logger.info("✓ R² TARGET ACHIEVED!")
        else:
            logger.warning(f"✗ R² below target. Gap: {0.9996 - self.metrics['r2']:.6f}")
        
        return self.metrics
    
    def get_feature_importance(self, feature_names):
        """
        Get feature importance with names
        
        Args:
            feature_names: List of feature names
            
        Returns:
            Sorted list of (feature, importance) tuples
        """
        importances = self.feature_importance.toArray()
        feature_importance_list = list(zip(feature_names, importances))
        feature_importance_list.sort(key=lambda x: x[1], reverse=True)
        
        logger.info("Top 10 most important features:")
        for i, (feature, importance) in enumerate(feature_importance_list[:10]):
            logger.info(f"{i+1}. {feature}: {importance:.4f} ({importance*100:.2f}%)")
        
        # Verify traffic_efficiency is top feature (should be ~81%)
        top_feature = feature_importance_list[0]
        if "traffic_efficiency" in top_feature[0]:
            logger.info(f"✓ traffic_efficiency is top feature at {top_feature[1]*100:.2f}%")
        
        return feature_importance_list
```

### Target Performance Criteria
- [ ] R² ≥ 0.9996
- [ ] RMSE ≤ 0.752
- [ ] MAE ≤ 0.289
- [ ] Model size ~27.9 MB
- [ ] traffic_efficiency ~81% feature importance

---

## Subtask 4.4: Gradient Boosted Trees Model

**Status**: Not Started

### Description
Train Gradient Boosted Trees as alternative high-performance model.

### Implementation Details

```python
# src/ml-training/models/gradient_boosted_trees.py
from pyspark.ml.regression import GBTRegressor
from pyspark.ml.evaluation import RegressionEvaluator
import logging

logger = logging.getLogger(__name__)

class GBTTrainer:
    """Train Gradient Boosted Trees model"""
    
    def __init__(self):
        self.model = None
        self.metrics = {}
    
    def train(self, train_df):
        """
        Train GBT model
        
        Target Performance:
        - R² = 0.9992
        - RMSE = 1.061
        
        Args:
            train_df: Training DataFrame
            
        Returns:
            Fitted model
        """
        logger.info("Training Gradient Boosted Trees model...")
        
        gbt = GBTRegressor(
            featuresCol="features",
            labelCol="label",
            maxIter=100,
            maxDepth=8,
            stepSize=0.1,
            seed=42
        )
        
        self.model = gbt.fit(train_df)
        
        logger.info("GBT training complete")
        
        return self.model
    
    def evaluate(self, test_df):
        """
        Evaluate GBT model
        
        Target: R² = 0.9992, RMSE = 1.061
        """
        logger.info("Evaluating GBT on test set...")
        
        predictions = self.model.transform(test_df)
        
        evaluator_rmse = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="rmse"
        )
        
        evaluator_r2 = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="r2"
        )
        
        evaluator_mae = RegressionEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="mae"
        )
        
        self.metrics = {
            "rmse": evaluator_rmse.evaluate(predictions),
            "r2": evaluator_r2.evaluate(predictions),
            "mae": evaluator_mae.evaluate(predictions)
        }
        
        logger.info(f"Test RMSE: {self.metrics['rmse']:.4f} (target: 1.061)")
        logger.info(f"Test R²: {self.metrics['r2']:.6f} (target: 0.9992)")
        logger.info(f"Test MAE: {self.metrics['mae']:.4f}")
        
        if self.metrics['r2'] >= 0.9992:
            logger.info("✓ R² TARGET ACHIEVED!")
        
        return self.metrics
```

### Target Performance Criteria
- [ ] R² ≥ 0.9992
- [ ] RMSE ≤ 1.061

---

## Subtask 4.5: 5-Fold Cross-Validation

**Status**: Not Started

### Description
Perform k-fold cross-validation to ensure model generalization.

### Implementation Details

```python
# src/ml-training/cross_validation.py
from pyspark.ml.tuning import CrossValidator
from pyspark.ml.evaluation import RegressionEvaluator
import logging

logger = logging.getLogger(__name__)

def perform_cross_validation(estimator, train_df, num_folds=5):
    """
    Perform k-fold cross-validation
    
    Args:
        estimator: ML model to validate
        train_df: Training data
        num_folds: Number of folds (default 5)
        
    Returns:
        Cross-validation results
    """
    logger.info(f"Performing {num_folds}-fold cross-validation...")
    
    evaluator = RegressionEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="r2"
    )
    
    cv = CrossValidator(
        estimator=estimator,
        estimatorParamMaps=[{}],  # No param grid, just CV
        evaluator=evaluator,
        numFolds=num_folds,
        seed=42
    )
    
    cv_model = cv.fit(train_df)
    
    # Get metrics from each fold
    avg_metrics = cv_model.avgMetrics[0]
    
    logger.info(f"Average R² across {num_folds} folds: {avg_metrics:.6f}")
    
    return cv_model, avg_metrics
```

### Validation Criteria
- [ ] 5-fold CV performed
- [ ] Average R² > 0.999 for Random Forest
- [ ] Standard deviation < 0.001 (consistent performance)

---

## Subtask 4.6: Model Persistence to HDFS

**Status**: Not Started

### Description
Save trained models to HDFS for use by prediction service. Expected Random Forest model size: 27.9 MB.

### Implementation Details

```python
# src/ml-training/model_persistence.py
from pyspark.ml import PipelineModel
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ModelPersistence:
    """Save and load ML models from HDFS"""
    
    HDFS_MODEL_BASE = "hdfs://namenode:9000/traffic-data/models/"
    
    def save_model(self, model, model_name, metrics, metadata=None):
        """
        Save model to HDFS with metadata
        
        Args:
            model: Trained Spark ML model
            model_name: Name for the model (e.g., "random_forest")
            metrics: Dictionary of evaluation metrics
            metadata: Optional additional metadata
            
        Returns:
            HDFS path where model was saved
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = f"{self.HDFS_MODEL_BASE}{model_name}/{timestamp}/"
        
        logger.info(f"Saving model to {model_path}")
        
        # Save model
        model.save(model_path + "model")
        
        # Save metadata
        metadata_dict = {
            "model_name": model_name,
            "timestamp": timestamp,
            "metrics": metrics,
            "model_path": model_path,
            **(metadata or {})
        }
        
        # Save as JSON (write locally first, then copy to HDFS)
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(metadata_dict, f, indent=2)
            temp_path = f.name
        
        # Copy to HDFS using hadoop fs command
        import subprocess
        subprocess.run([
            "hadoop", "fs", "-put", "-f",
            temp_path,
            model_path + "metadata.json"
        ])
        
        os.remove(temp_path)
        
        logger.info(f"Model saved successfully to {model_path}")
        logger.info(f"Model metrics: {metrics}")
        
        # Verify model size
        size_result = subprocess.run([
            "hadoop", "fs", "-du", "-h",
            model_path
        ], capture_output=True, text=True)
        
        logger.info(f"Model size: {size_result.stdout}")
        
        return model_path
    
    def load_model(self, model_path, model_type="RandomForestRegressionModel"):
        """
        Load model from HDFS
        
        Args:
            model_path: Full HDFS path to model
            model_type: Type of model to load
            
        Returns:
            Loaded model
        """
        logger.info(f"Loading model from {model_path}")
        
        from pyspark.ml.regression import RandomForestRegressionModel, GBTRegressionModel, LinearRegressionModel
        
        model_classes = {
            "RandomForestRegressionModel": RandomForestRegressionModel,
            "GBTRegressionModel": GBTRegressionModel,
            "LinearRegressionModel": LinearRegressionModel
        }
        
        model_class = model_classes.get(model_type)
        if not model_class:
            raise ValueError(f"Unknown model type: {model_type}")
        
        model = model_class.load(model_path + "model")
        
        logger.info("Model loaded successfully")
        
        return model
    
    def get_latest_model(self, model_name):
        """
        Get path to latest version of a model
        
        Args:
            model_name: Model name (e.g., "random_forest")
            
        Returns:
            Path to latest model
        """
        import subprocess
        
        base_path = f"{self.HDFS_MODEL_BASE}{model_name}/"
        
        # List all versions
        result = subprocess.run([
            "hadoop", "fs", "-ls",
            base_path
        ], capture_output=True, text=True)
        
        # Parse output to get latest timestamp
        versions = []
        for line in result.stdout.split('\n'):
            if base_path in line:
                version = line.split()[-1].replace(base_path, '').strip('/')
                versions.append(version)
        
        if not versions:
            raise FileNotFoundError(f"No models found at {base_path}")
        
        latest = sorted(versions)[-1]
        latest_path = f"{base_path}{latest}/"
        
        logger.info(f"Latest model version: {latest}")
        
        return latest_path
```

**Storage Structure**:
```
/traffic-data/models/
  random_forest/
    20240107_143000/
      model/
        metadata/
        data/
        treesMetadata/
      metadata.json
    20240107_150000/
      ...
  gradient_boosted_trees/
    ...
  linear_regression/
    ...
```

### Validation Criteria
- [ ] Random Forest model saved (~27.9 MB)
- [ ] GBT model saved
- [ ] Linear Regression model saved
- [ ] Metadata JSON files created
- [ ] Models loadable from HDFS
- [ ] Latest model retrieval works

---

## Complete Training Pipeline

```python
# src/ml-training/train_all_models.py
from pyspark.sql import SparkSession
from data_loader import TrafficDataLoader
from models.linear_regression import LinearRegressionTrainer
from models.random_forest import RandomForestTrainer
from models.gradient_boosted_trees import GBTTrainer
from model_persistence import ModelPersistence
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Train all traffic prediction models"""
    
    # Initialize Spark
    spark = SparkSession.builder \
        .appName("TrafficPredictionModelTraining") \
        .config("spark.sql.shuffle.partitions", "10") \
        .getOrCreate()
    
    # Load and prepare data
    logger.info("=" * 80)
    logger.info("LOADING AND PREPARING DATA")
    logger.info("=" * 80)
    
    loader = TrafficDataLoader(spark)
    df = loader.load_features("hdfs://namenode:9000/traffic-data/processed/ml-features/")
    df_prepared, preprocessing_model = loader.prepare_features(df)
    train_df, test_df = loader.train_test_split(df_prepared)
    
    # Save preprocessing model
    persistence = ModelPersistence()
    preprocessing_model.save("hdfs://namenode:9000/traffic-data/models/preprocessing/model")
    
    # Train models
    results = {}
    
    # 1. Linear Regression (Baseline)
    logger.info("=" * 80)
    logger.info("TRAINING LINEAR REGRESSION (BASELINE)")
    logger.info("=" * 80)
    
    lr_trainer = LinearRegressionTrainer()
    lr_model = lr_trainer.train(train_df)
    lr_metrics = lr_trainer.evaluate(test_df)
    results['linear_regression'] = lr_metrics
    
    persistence.save_model(
        lr_model,
        "linear_regression",
        lr_metrics,
        {"type": "baseline"}
    )
    
    # 2. Random Forest (PRIMARY MODEL - Target: R²=0.9996)
    logger.info("=" * 80)
    logger.info("TRAINING RANDOM FOREST (PRIMARY MODEL)")
    logger.info("=" * 80)
    
    rf_trainer = RandomForestTrainer()
    rf_model = rf_trainer.train(train_df, tune_hyperparameters=True)
    rf_metrics = rf_trainer.evaluate(test_df)
    results['random_forest'] = rf_metrics
    
    # Get feature importance
    feature_names = loader.numeric_features + [
        f"{c}_encoded" for c in loader.categorical_features
    ]
    rf_feature_importance = rf_trainer.get_feature_importance(feature_names)
    
    persistence.save_model(
        rf_model,
        "random_forest",
        rf_metrics,
        {
            "type": "primary",
            "feature_importance": {name: float(imp) for name, imp in rf_feature_importance}
        }
    )
    
    # 3. Gradient Boosted Trees
    logger.info("=" * 80)
    logger.info("TRAINING GRADIENT BOOSTED TREES")
    logger.info("=" * 80)
    
    gbt_trainer = GBTTrainer()
    gbt_model = gbt_trainer.train(train_df)
    gbt_metrics = gbt_trainer.evaluate(test_df)
    results['gradient_boosted_trees'] = gbt_metrics
    
    persistence.save_model(
        gbt_model,
        "gradient_boosted_trees",
        gbt_metrics,
        {"type": "alternative"}
    )
    
    # Summary
    logger.info("=" * 80)
    logger.info("TRAINING COMPLETE - SUMMARY")
    logger.info("=" * 80)
    
    for model_name, metrics in results.items():
        logger.info(f"\n{model_name.upper()}:")
        logger.info(f"  R²: {metrics['r2']:.6f}")
        logger.info(f"  RMSE: {metrics['rmse']:.4f}")
        logger.info(f"  MAE: {metrics['mae']:.4f}")
    
    # Check if Random Forest met target
    if results['random_forest']['r2'] >= 0.9996:
        logger.info("\n✓✓✓ RANDOM FOREST ACHIEVED TARGET R² ≥ 0.9996 ✓✓✓")
    else:
        logger.warning(f"\n✗✗✗ Random Forest R² below target: {results['random_forest']['r2']:.6f} ✗✗✗")
    
    spark.stop()

if __name__ == "__main__":
    main()
```

**Execution**:
```bash
spark-submit \
  --master spark://spark-master:7077 \
  --executor-memory 4G \
  --driver-memory 2G \
  --total-executor-cores 4 \
  src/ml-training/train_all_models.py
```

---

## Completion Criteria

### Phase 4 Complete When:
- [ ] Data loaded from HDFS ml-features
- [ ] Features preprocessed (scaled, encoded)
- [ ] Linear Regression trained (baseline)
- [ ] Random Forest trained with R² ≥ 0.9996, RMSE ≤ 0.752
- [ ] Gradient Boosted Trees trained with R² ≥ 0.9992
- [ ] 5-fold cross-validation performed
- [ ] All models saved to HDFS
- [ ] Random Forest ~27.9 MB
- [ ] traffic_efficiency confirmed as top feature (~81%)
- [ ] Model loading from HDFS verified

### Performance Targets
- **Random Forest**: R²=0.9996, RMSE=0.752, MAE=0.289 ✓
- **GBT**: R²=0.9992, RMSE=1.061 ✓
- **Training time**: < 10 minutes on sample data
- **Model size**: Random Forest ~27.9 MB

---

## Next Steps
→ Proceed to **Task 5: Real-time Prediction Service**
