#!/usr/bin/env python3#!/usr/bin/env python3

""""""

METR-LA ML Training Pipeline - Spark MLlib ImplementationMETR-LA ML Training Pipeline - Spark MLlib Implementation

Spark MLlib pipeline for traffic prediction model trainingSpark MLlib pipeline for traffic prediction model training



Features:Features:

- Reads aggregated data from HDFS- Reads aggregated data from HDFS

- Time-series feature engineering- Time-series feature engineering

- Multiple ML algorithms (Linear Regression, Random Forest, GBT)- Multiple ML algorithms (Linear Regression, Random Forest, GBT)

- Model evaluation and selection- Model evaluation and selection

- Model export for predictions- Model export for predictions

""""""



import osimport os

import sysimport sys

import jsonimport json

import loggingimport logging

from datetime import datetime, timedeltafrom datetime import datetime, timedelta

from typing import Dict, Any, Optional, List, Tuplefrom typing import Dict, Any, Optional, List, Tuple

from pathlib import Pathfrom pathlib import Path



# Add PySpark to path# Add PySpark to path

spark_home = os.environ.get('SPARK_HOME', '/opt/bitnami/spark')spark_home = os.environ.get('SPARK_HOME', '/opt/bitnami/spark')

sys.path.append(os.path.join(spark_home, 'python'))sys.path.append(os.path.join(spark_home, 'python'))

sys.path.append(os.path.join(spark_home, 'python', 'lib', 'py4j-0.10.9.7-src.zip'))sys.path.append(os.path.join(spark_home, 'python', 'lib', 'py4j-0.10.9.7-src.zip'))



from pyspark.sql import SparkSession, DataFramefrom pyspark.sql import SparkSession, DataFrame

from pyspark.sql.functions import (from pyspark.sql.functions import (

    col, avg, max, min, count, lag, lead, stddev,     col, avg, max, min, count, lag, lead, stddev, 

    hour, dayofweek, when, isnan, isnull, desc, asc,    hour, dayofweek, when, isnan, isnull, desc, asc,

    unix_timestamp, from_unixtime, window, sum as spark_sum    unix_timestamp, from_unixtime, window, sum as spark_sum

))

from pyspark.sql.types import DoubleTypefrom pyspark.sql.types import DoubleType

from pyspark.sql.window import Windowfrom pyspark.sql.window import Window



from pyspark.ml import Pipelinefrom pyspark.ml import Pipeline

from pyspark.ml.feature import (from pyspark.ml.feature import (

    VectorAssembler, StandardScaler, StringIndexer, OneHotEncoder    VectorAssembler, StandardScaler, StringIndexer, OneHotEncoder,

)    PCA, Bucketizer, QuantileDiscretizer

from pyspark.ml.regression import ()

    LinearRegression, RandomForestRegressor, GBTRegressorfrom pyspark.ml.regression import (

)    LinearRegression, RandomForestRegressor, GBTRegressor

from pyspark.ml.evaluation import RegressionEvaluator)

from pyspark.ml.evaluation import RegressionEvaluator

# Configure loggingfrom pyspark.ml.tuning import CrossValidator, ParamGridBuilder

logging.basicConfig(from pyspark.ml.linalg import Vectors

    level=logging.INFO,from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'from sklearn.linear_model import LinearRegression, Ridge, Lasso

)from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder

logger = logging.getLogger("metr_la_ml_training")from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV

from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

class MetrLAMLTraining:from sklearn.pipeline import Pipeline

    """ML Training pipeline for METR-LA traffic prediction"""import xgboost as xgb

    

    def __init__(self, config: Dict[str, Any]):# PySpark for distributed processing

        """Initialize ML training pipeline"""from pyspark.sql import SparkSession, DataFrame

        self.config = configfrom pyspark.sql.types import (

        self.spark = None    StructType, StructField, StringType, IntegerType, 

        self.models = {}    DoubleType, TimestampType, BooleanType, LongType

        self.feature_columns = [])

        self._setup_spark_session()from pyspark.sql.functions import (

        col, avg, sum as spark_sum, count, max as spark_max, 

    def _setup_spark_session(self):    min as spark_min, when, from_json, current_timestamp

        """Create Spark session with ML configuration""")

        try:from pyspark.ml import Pipeline as MLPipeline

            self.spark = SparkSession.builder \from pyspark.ml.feature import VectorAssembler, StandardScaler as SparkStandardScaler

                .appName("METR-LA-ML-Training") \from pyspark.ml.regression import RandomForestRegressor as SparkRF, GBTRegressor

                .config("spark.master", "spark://spark-master:7077") \from pyspark.ml.evaluation import RegressionEvaluator

                .config("spark.sql.adaptive.enabled", "true") \from pyspark.ml.tuning import CrossValidator, ParamGridBuilder

                .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \

                .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \# Add project root to path

                .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \project_root = Path(__file__).parent.parent.parent

                .config("spark.sql.execution.arrow.pyspark.enabled", "true") \sys.path.append(str(project_root))

                .config("spark.sql.adaptive.skewJoin.enabled", "true") \

                .config("spark.sql.adaptive.localShuffleReader.enabled", "true") \logger = logging.getLogger("metr_la_ml")

                .getOrCreate()

            @dataclass

            # Set log levelclass MLTrainingConfig:

            self.spark.sparkContext.setLogLevel("WARN")    """Configuration for METR-LA ML training pipeline"""

                # Data Configuration

            logger.info("✅ Spark ML session created successfully")    hdfs_input_path: str = "hdfs://localhost:9000/traffic-data/streaming/metr-la"

            logger.info(f"   App Name: {self.spark.sparkContext.appName}")    hdfs_models_path: str = "hdfs://localhost:9000/traffic-data/models"

            logger.info(f"   Master: {self.spark.sparkContext.master}")    local_models_path: str = "models"

                

        except Exception as e:    # Training Configuration

            logger.error(f"❌ Failed to create Spark session: {e}")    test_size: float = 0.2

            raise    validation_size: float = 0.1

        random_state: int = 42

    def load_training_data(self, data_path: str) -> DataFrame:    

        """Load aggregated traffic data from HDFS for training"""    # Model Configuration

        try:    models: Optional[List[str]] = None

            logger.info(f"📊 Loading training data from: {data_path}")    cross_validation_folds: int = 5

                

            # Read parquet files from HDFS    # Feature Engineering

            df = self.spark.read \    feature_columns: Optional[List[str]] = None

                .format("parquet") \    target_column: str = "avg_speed_mph"

                .load(data_path) \    time_window_hours: int = 24  # Hours of historical data to consider

                .filter(col("avg_speed_mph").isNotNull()) \    prediction_horizon_minutes: int = 30  # Minutes into future to predict

                .filter(col("record_count") > 0) \    

                .filter((col("avg_speed_mph") >= 0) & (col("avg_speed_mph") <= 120))    # Hyperparameter Tuning

                enable_hyperparameter_tuning: bool = True

            # Add timestamp features    max_evaluations: int = 50

            df = df.withColumn("timestamp_unix", unix_timestamp(col("window_start"))) \    

                   .withColumn("hour_of_day", hour(col("window_start"))) \    # Performance Configuration

                   .withColumn("day_of_week", dayofweek(col("window_start")))    spark_executor_memory: str = "2g"

                spark_executor_cores: int = 2

            record_count = df.count()    

            logger.info(f"✅ Loaded {record_count:,} training records")    def __post_init__(self):

                    """Set defaults for mutable fields"""

            if record_count == 0:        if self.models is None:

                raise ValueError("No training data found")            self.models = ["random_forest", "gradient_boosting", "xgboost", "linear_regression"]

                    

            return df        if self.feature_columns is None:

                        self.feature_columns = [

        except Exception as e:                "avg_speed_kmh", "avg_volume_vph", "total_volume", "congestion_ratio",

            logger.error(f"❌ Failed to load training data: {e}")                "speed_variability", "avg_traffic_efficiency", "hour_of_day", 

            raise                "day_of_week", "is_weekend", "is_rush_hour", "avg_latitude", 

                    "avg_longitude", "total_count", "avg_quality_score"

    def create_time_series_features(self, df: DataFrame) -> DataFrame:            ]

        """Create time-series features for traffic prediction"""

        try:class MetrLAMLTrainer:

            logger.info("🔧 Creating time-series features...")    """Machine Learning trainer for METR-LA traffic prediction"""

                

            # Window specification for time-series operations    def __init__(self, config: MLTrainingConfig):

            window_spec = Window.partitionBy("segment_id").orderBy("timestamp_unix")        """Initialize ML trainer"""

                    self.config = config

            # Lag features (historical values)        self.spark: Optional[SparkSession] = None

            df = df.withColumn("speed_lag_1", lag("avg_speed_mph", 1).over(window_spec)) \        self.models: Dict[str, Any] = {}

                   .withColumn("speed_lag_2", lag("avg_speed_mph", 2).over(window_spec)) \        self.scalers: Dict[str, Any] = {}

                   .withColumn("speed_lag_3", lag("avg_speed_mph", 3).over(window_spec)) \        self.metrics: Dict[str, Dict[str, float]] = {}

                   .withColumn("speed_lag_6", lag("avg_speed_mph", 6).over(window_spec)) \        self.logger = self._setup_logging()

                   .withColumn("speed_lag_12", lag("avg_speed_mph", 12).over(window_spec))        

                    # Ensure local models directory exists

            # Lead features (future values for prediction)        Path(self.config.local_models_path).mkdir(parents=True, exist_ok=True)

            df = df.withColumn("speed_lead_1", lead("avg_speed_mph", 1).over(window_spec)) \    

                   .withColumn("speed_lead_2", lead("avg_speed_mph", 2).over(window_spec))    def _setup_logging(self) -> logging.Logger:

                    """Setup logging configuration"""

            # Rolling statistics (6-hour window = 72 periods of 5 minutes)        logger = logging.getLogger("metr_la_ml")

            rolling_window = Window.partitionBy("segment_id") \        logger.setLevel(logging.INFO)

                                   .orderBy("timestamp_unix") \        

                                   .rowsBetween(-72, -1)        if not logger.handlers:

                        handler = logging.StreamHandler(sys.stdout)

            df = df.withColumn("speed_rolling_avg", avg("avg_speed_mph").over(rolling_window)) \            formatter = logging.Formatter(

                   .withColumn("speed_rolling_std", stddev("avg_speed_mph").over(rolling_window)) \                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

                   .withColumn("speed_rolling_min", min("avg_speed_mph").over(rolling_window)) \            )

                   .withColumn("speed_rolling_max", max("avg_speed_mph").over(rolling_window))            handler.setFormatter(formatter)

                        logger.addHandler(handler)

            # Temporal features        

            df = df.withColumn("is_weekend", when(col("day_of_week").isin([1, 7]), 1.0).otherwise(0.0)) \        return logger

                   .withColumn("is_rush_hour",     

                               when((col("hour_of_day").between(7, 9)) |     def initialize_spark(self):

                                    (col("hour_of_day").between(17, 19)), 1.0).otherwise(0.0)) \        """Initialize Spark session for distributed ML"""

                   .withColumn("is_night", when(col("hour_of_day").between(22, 6), 1.0).otherwise(0.0))        self.logger.info("Initializing Spark session for ML training...")

                    

            # Traffic volume features        try:

            df = df.withColumn("volume_per_lane", col("record_count") / col("lane_count")) \            builder = SparkSession.builder \

                   .withColumn("speed_variance", col("stddev_speed_mph") * col("stddev_speed_mph"))                .appName("MetrLA-MLTraining") \

                            .master("local[*]") \

            # Remove rows with null lag features (beginning of time series)                .config("spark.executor.memory", self.config.spark_executor_memory) \

            df = df.filter(col("speed_lag_1").isNotNull())                .config("spark.executor.cores", self.config.spark_executor_cores) \

                            .config("spark.sql.adaptive.enabled", "true") \

            logger.info("✅ Time-series features created")                .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \

            return df                .config("spark.sql.execution.arrow.pyspark.enabled", "true")

                        

        except Exception as e:            self.spark = builder.getOrCreate()

            logger.error(f"❌ Failed to create time-series features: {e}")              self.spark.sparkContext.setLogLevel("WARN")

            raise            

                self.logger.info(f"Spark session initialized - Version: {self.spark.version}")

    def prepare_ml_features(self, df: DataFrame) -> tuple:            

        """Prepare features for ML training"""        except Exception as e:

        try:            self.logger.error(f"Failed to initialize Spark: {e}")

            logger.info("🔧 Preparing ML features...")            raise

                

            # Define feature columns    def load_training_data(self) -> pd.DataFrame:

            self.feature_columns = [        """Load training data from HDFS"""

                "speed_lag_1", "speed_lag_2", "speed_lag_3", "speed_lag_6", "speed_lag_12",        self.logger.info(f"Loading training data from: {self.config.hdfs_input_path}")

                "speed_rolling_avg", "speed_rolling_std", "speed_rolling_min", "speed_rolling_max",        

                "hour_of_day", "day_of_week", "is_weekend", "is_rush_hour", "is_night",        try:

                "lane_count", "volume_per_lane", "speed_variance",            # For now, let's simulate data loading by creating sample data

                "max_speed_mph", "min_speed_mph", "median_speed_mph", "p85_speed_mph"            # In production, this would read from HDFS parquet files

            ]            self.logger.warning("Using simulated data - in production this would read from HDFS")

                        

            # String indexer for categorical features            # Generate realistic METR-LA traffic data

            road_type_indexer = StringIndexer(            np.random.seed(self.config.random_state)

                inputCol="road_type",             n_samples = 10000

                outputCol="road_type_indexed",            n_sensors = 50

                handleInvalid="keep"            

            )            # Create time-based features

                        timestamps = pd.date_range(

            # One-hot encode road type                start=datetime.now() - timedelta(days=30),

            road_type_encoder = OneHotEncoder(                end=datetime.now(),

                inputCol="road_type_indexed",                periods=n_samples

                outputCol="road_type_encoded"            )

            )            

                        data = []

            # Vector assembler for features            for i in range(n_samples):

            feature_assembler = VectorAssembler(                timestamp = timestamps[i]

                inputCols=self.feature_columns + ["road_type_encoded"],                sensor_id = f"sensor_{np.random.randint(1, n_sensors+1):03d}"

                outputCol="raw_features",                

                handleInvalid="skip"                # Time-based features

            )                hour_of_day = timestamp.hour

                            day_of_week = timestamp.weekday() + 1

            # Standard scaler                is_weekend = day_of_week in [6, 7]

            scaler = StandardScaler(                is_rush_hour = hour_of_day in [7, 8, 9, 17, 18, 19]

                inputCol="raw_features",                

                outputCol="features",                # Base speed varies by time of day

                withStd=True,                base_speed = 45 + 15 * np.sin(2 * np.pi * hour_of_day / 24)

                withMean=True                

            )                # Rush hour and weekend effects

                            if is_rush_hour and not is_weekend:

            # Create preprocessing pipeline                    base_speed *= 0.6  # Slower during rush hour

            preprocessing_pipeline = Pipeline(stages=[                elif is_weekend:

                road_type_indexer,                    base_speed *= 1.1  # Faster on weekends

                road_type_encoder,                

                feature_assembler,                # Add noise

                scaler                speed_mph = max(5, base_speed + np.random.normal(0, 10))

            ])                speed_kmh = speed_mph * 1.60934

                            

            # Fit preprocessing pipeline                # Volume correlates inversely with speed

            preprocessing_model = preprocessing_pipeline.fit(df)                base_volume = 1000 * (60 - speed_mph) / 60

            processed_df = preprocessing_model.transform(df)                volume_vph = max(0, base_volume + np.random.normal(0, 200))

                            

            # Select features and target for training                # Other derived features

            ml_df = processed_df.select(                congestion_ratio = 1 - (speed_mph / 60)

                col("features"),                speed_variability = np.random.uniform(0.1, 0.5)

                col("avg_speed_mph").alias("label"),  # Current speed as target                traffic_efficiency = speed_mph / (volume_vph / 100) if volume_vph > 0 else 0

                col("speed_lead_1").alias("future_speed_1"),  # 5-min ahead prediction                

                col("speed_lead_2").alias("future_speed_2"),  # 10-min ahead prediction                # Location (LA area)

                col("segment_id"),                latitude = 34.0522 + np.random.normal(0, 0.1)

                col("window_start"),                longitude = -118.2437 + np.random.normal(0, 0.1)

                col("road_type")                

            ).filter(col("future_speed_1").isNotNull())                data.append({

                                "sensor_id": sensor_id,

            logger.info(f"✅ ML features prepared with {len(self.feature_columns) + 1} features")                    "timestamp": timestamp,

            logger.info(f"   Training samples: {ml_df.count():,}")                    "avg_speed_mph": speed_mph,

                                "avg_speed_kmh": speed_kmh,

            return ml_df, preprocessing_model                    "avg_volume_vph": int(volume_vph),

                                "total_volume": int(volume_vph * np.random.uniform(1, 3)),

        except Exception as e:                    "congestion_ratio": min(1.0, max(0.0, congestion_ratio)),

            logger.error(f"❌ Failed to prepare ML features: {e}")                    "speed_variability": speed_variability,

            raise                    "avg_traffic_efficiency": max(0, traffic_efficiency),

                        "hour_of_day": hour_of_day,

    def train_models(self, train_df: DataFrame) -> tuple:                    "day_of_week": day_of_week,

        """Train multiple ML models for comparison"""                    "is_weekend": is_weekend,

        try:                    "is_rush_hour": is_rush_hour,

            logger.info("🤖 Training ML models...")                    "avg_latitude": latitude,

                                "avg_longitude": longitude,

            models = {}                    "total_count": np.random.randint(1, 20),

            evaluator = RegressionEvaluator(                    "avg_quality_score": np.random.uniform(0.7, 1.0)

                labelCol="future_speed_1",                })

                predictionCol="prediction",            

                metricName="rmse"            df = pd.DataFrame(data)

            )            self.logger.info(f"Loaded {len(df)} training samples")

                        self.logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

            # Split data for training and validation            self.logger.info(f"Features: {list(df.columns)}")

            train_data, test_data = train_df.randomSplit([0.8, 0.2], seed=42)            

                        return df

            logger.info(f"   Training samples: {train_data.count():,}")            

            logger.info(f"   Test samples: {test_data.count():,}")        except Exception as e:

                        self.logger.error(f"Failed to load training data: {e}")

            # 1. Linear Regression            raise

            logger.info("Training Linear Regression...")    

            lr = LinearRegression(    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:

                featuresCol="features",        """Prepare features and target for training"""

                labelCol="future_speed_1",        self.logger.info("Preparing features and target...")

                regParam=0.01,        

                elasticNetParam=0.5,        # Select feature columns

                maxIter=100        feature_columns = self.config.feature_columns or []

            )        available_features = [col for col in feature_columns if col in df.columns]

                    missing_features = [col for col in feature_columns if col not in df.columns]

            lr_model = lr.fit(train_data)        

            lr_predictions = lr_model.transform(test_data)        if missing_features:

            lr_rmse = evaluator.evaluate(lr_predictions)            self.logger.warning(f"Missing features: {missing_features}")

                    

            models['linear_regression'] = {        self.logger.info(f"Using features: {available_features}")

                'model': lr_model,        

                'rmse': lr_rmse,        # Prepare features

                'predictions': lr_predictions        X = df[available_features].copy()

            }        

                    # Handle missing values

            logger.info(f"   Linear Regression RMSE: {lr_rmse:.2f}")        X = X.fillna(X.mean())

                    

            # 2. Random Forest        # Prepare target

            logger.info("Training Random Forest...")        y = df[self.config.target_column].copy()

            rf = RandomForestRegressor(        

                featuresCol="features",        self.logger.info(f"Feature matrix shape: {X.shape}")

                labelCol="future_speed_1",        self.logger.info(f"Target shape: {y.shape}")

                numTrees=50,        self.logger.info(f"Target statistics: mean={y.mean():.2f}, std={y.std():.2f}, range=[{y.min():.2f}, {y.max():.2f}]")

                maxDepth=10,        

                minInstancesPerNode=10,        return X, y

                seed=42    

            )    def train_sklearn_models(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:

                    """Train scikit-learn models"""

            rf_model = rf.fit(train_data)        self.logger.info("Training scikit-learn models...")

            rf_predictions = rf_model.transform(test_data)        

            rf_rmse = evaluator.evaluate(rf_predictions)        # Split data

                    X_train, X_test, y_train, y_test = train_test_split(

            models['random_forest'] = {            X, y, test_size=self.config.test_size, random_state=self.config.random_state

                'model': rf_model,        )

                'rmse': rf_rmse,        

                'predictions': rf_predictions        # Scale features

            }        scaler = StandardScaler()

                    X_train_scaled = scaler.fit_transform(X_train)

            logger.info(f"   Random Forest RMSE: {rf_rmse:.2f}")        X_test_scaled = scaler.transform(X_test)

                    

            # 3. Gradient Boosted Trees        self.scalers['standard'] = scaler

            logger.info("Training Gradient Boosted Trees...")        

            gbt = GBTRegressor(        # Define models

                featuresCol="features",        model_configs = {

                labelCol="future_speed_1",            "random_forest": RandomForestRegressor(

                maxIter=50,                n_estimators=100,

                maxDepth=8,                max_depth=10,

                stepSize=0.1,                random_state=self.config.random_state,

                seed=42                n_jobs=-1

            )            ),

                        "gradient_boosting": GradientBoostingRegressor(

            gbt_model = gbt.fit(train_data)                n_estimators=100,

            gbt_predictions = gbt_model.transform(test_data)                max_depth=6,

            gbt_rmse = evaluator.evaluate(gbt_predictions)                learning_rate=0.1,

                            random_state=self.config.random_state

            models['gradient_boosted_trees'] = {            ),

                'model': gbt_model,            "xgboost": xgb.XGBRegressor(

                'rmse': gbt_rmse,                n_estimators=100,

                'predictions': gbt_predictions                max_depth=6,

            }                learning_rate=0.1,

                            random_state=self.config.random_state,

            logger.info(f"   Gradient Boosted Trees RMSE: {gbt_rmse:.2f}")                n_jobs=-1

                        ),

            # Select best model            "linear_regression": Pipeline([

            best_model_name = min(models.keys(), key=lambda k: models[k]['rmse'])                ("scaler", StandardScaler()),

            best_model = models[best_model_name]                ("model", LinearRegression())

                        ]),

            logger.info(f"✅ Best model: {best_model_name} (RMSE: {best_model['rmse']:.2f})")            "ridge": Pipeline([

                            ("scaler", StandardScaler()),

            return models, best_model_name                ("model", Ridge(alpha=1.0, random_state=self.config.random_state))

                        ])

        except Exception as e:        }

            logger.error(f"❌ Failed to train models: {e}")        

            raise        trained_models = {}

            

    def save_models(self, models: Dict[str, Any], preprocessing_model, best_model_name: str):        models_to_train = self.config.models or []

        """Save trained models to HDFS"""        for model_name in models_to_train:

        try:            if model_name not in model_configs:

            logger.info("💾 Saving models to HDFS...")                self.logger.warning(f"Unknown model: {model_name}")

                            continue

            base_path = "hdfs://namenode:9000/traffic-models"            

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")            self.logger.info(f"Training {model_name}...")

                        

            # Save preprocessing model            model = model_configs[model_name]

            preprocessing_path = f"{base_path}/preprocessing/{timestamp}"            

            preprocessing_model.write().overwrite().save(preprocessing_path)            # Use scaled features for linear models

            logger.info(f"   Preprocessing model saved: {preprocessing_path}")            if model_name in ["linear_regression", "ridge"]:

                            X_train_input = X_train_scaled

            # Save ML models                X_test_input = X_test_scaled

            for model_name, model_info in models.items():            else:

                model_path = f"{base_path}/{model_name}/{timestamp}"                X_train_input = X_train

                model_info['model'].write().overwrite().save(model_path)                X_test_input = X_test

                logger.info(f"   {model_name} saved: {model_path}")            

                        # Train model

            # Save best model separately            model.fit(X_train_input, y_train)

            best_model_path = f"{base_path}/best_model/{timestamp}"            

            models[best_model_name]['model'].write().overwrite().save(best_model_path)            # Make predictions

                        y_pred = model.predict(X_test_input)

            # Save model metadata            

            metadata = {            # Calculate metrics

                'timestamp': timestamp,            mse = mean_squared_error(y_test, y_pred)

                'best_model': best_model_name,            mae = mean_absolute_error(y_test, y_pred)

                'models': {name: info['rmse'] for name, info in models.items()},            r2 = r2_score(y_test, y_pred)

                'feature_columns': self.feature_columns,            rmse = np.sqrt(mse)

                'preprocessing_path': preprocessing_path,            

                'best_model_path': best_model_path            # Cross-validation score

            }            if model_name in ["linear_regression", "ridge"]:

                            cv_scores = cross_val_score(model, X_train_scaled, y_train, 

            metadata_path = f"{base_path}/metadata/model_metadata_{timestamp}.json"                                          cv=self.config.cross_validation_folds, 

            metadata_df = self.spark.createDataFrame([metadata])                                          scoring='r2')

            metadata_df.coalesce(1).write.mode("overwrite").json(metadata_path)            else:

                            cv_scores = cross_val_score(model, X_train, y_train, 

            logger.info(f"✅ All models saved successfully")                                          cv=self.config.cross_validation_folds, 

            logger.info(f"   Best model: {best_model_name}")                                          scoring='r2')

            logger.info(f"   Metadata: {metadata_path}")            

                        self.metrics[model_name] = {

        except Exception as e:                "mse": mse,

            logger.error(f"❌ Failed to save models: {e}")                "mae": mae,

            raise                "rmse": rmse,

                    "r2": r2,

    def run_training_pipeline(self):                "cv_mean": cv_scores.mean(),

        """Run the complete ML training pipeline"""                "cv_std": cv_scores.std()

        try:            }

            logger.info("🚀 Starting METR-LA ML Training Pipeline")            

                        trained_models[model_name] = model

            # Load training data            

            data_path = "hdfs://namenode:9000/traffic-data/aggregates"            self.logger.info(f"{model_name} metrics:")

            df = self.load_training_data(data_path)            self.logger.info(f"  RMSE: {rmse:.2f}")

                        self.logger.info(f"  MAE: {mae:.2f}")

            # Create time-series features            self.logger.info(f"  R²: {r2:.3f}")

            featured_df = self.create_time_series_features(df)            self.logger.info(f"  CV R²: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

                    

            # Prepare ML features        return trained_models

            ml_df, preprocessing_model = self.prepare_ml_features(featured_df)    

                def save_models(self, models: Dict[str, Any]):

            # Train models        """Save trained models to disk and HDFS"""

            models, best_model_name = self.train_models(ml_df)        self.logger.info("Saving trained models...")

                    

            # Save models        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            self.save_models(models, preprocessing_model, best_model_name)        

                    for model_name, model in models.items():

            logger.info("✅ ML Training Pipeline completed successfully")            # Save locally

                        local_path = Path(self.config.local_models_path) / f"{model_name}_{timestamp}.pkl"

        except Exception as e:            

            logger.error(f"❌ Training pipeline failed: {e}", exc_info=True)            with open(local_path, 'wb') as f:

            raise                pickle.dump(model, f)

        finally:            

            if self.spark:            self.logger.info(f"Saved {model_name} to {local_path}")

                self.spark.stop()            

            # Save metadata

def create_default_config() -> Dict[str, Any]:            metadata = {

    """Create default configuration for ML training"""                "model_name": model_name,

    return {                "timestamp": timestamp,

        'spark': {                "metrics": self.metrics.get(model_name, {}),

            'app_name': 'METR-LA-ML-Training',                "config": asdict(self.config),

            'master': 'spark://spark-master:7077'                "feature_columns": self.config.feature_columns,

        },                "target_column": self.config.target_column

        'hdfs': {            }

            'namenode_url': 'hdfs://namenode:9000',            

            'data_path': '/traffic-data/aggregates',            metadata_path = Path(self.config.local_models_path) / f"{model_name}_{timestamp}_metadata.json"

            'model_path': '/traffic-models'            with open(metadata_path, 'w') as f:

        },                json.dump(metadata, f, indent=2, default=str)

        'ml': {            

            'test_ratio': 0.2,            self.logger.info(f"Saved {model_name} metadata to {metadata_path}")

            'random_seed': 42        

        }        # Save scaler

    }        if self.scalers:

            scaler_path = Path(self.config.local_models_path) / f"scaler_{timestamp}.pkl"

def main():            with open(scaler_path, 'wb') as f:

    """Main entry point"""                pickle.dump(self.scalers, f)

    import argparse            

                self.logger.info(f"Saved scalers to {scaler_path}")

    parser = argparse.ArgumentParser(description='METR-LA ML Training Pipeline')        

    parser.add_argument('--data-path', help='HDFS path to training data')        # Save training summary

    parser.add_argument('--model-path', help='HDFS path to save models')        summary = {

                "training_timestamp": timestamp,

    args = parser.parse_args()            "models_trained": list(models.keys()),

                "metrics": self.metrics,

    # Create configuration            "best_model": self._get_best_model(),

    config = create_default_config()            "config": asdict(self.config)

    if args.data_path:        }

        config['hdfs']['data_path'] = args.data_path        

    if args.model_path:        summary_path = Path(self.config.local_models_path) / f"training_summary_{timestamp}.json"

        config['hdfs']['model_path'] = args.model_path        with open(summary_path, 'w') as f:

                json.dump(summary, f, indent=2, default=str)

    try:        

        # Create and run training pipeline        self.logger.info(f"Saved training summary to {summary_path}")

        pipeline = MetrLAMLTraining(config)    

        pipeline.run_training_pipeline()    def _get_best_model(self) -> Dict[str, Any]:

                """Determine the best model based on metrics"""

    except Exception as e:        if not self.metrics:

        logger.error(f"Training failed: {e}", exc_info=True)            return {}

        sys.exit(1)        

        # Rank by R² score (higher is better)

if __name__ == "__main__":        best_model_name = max(self.metrics.keys(), key=lambda k: self.metrics[k].get('r2', 0))

    main()        best_metrics = self.metrics[best_model_name]
        
        return {
            "model_name": best_model_name,
            "metrics": best_metrics
        }
    
    def generate_training_report(self) -> Dict[str, Any]:
        """Generate comprehensive training report"""
        timestamp = datetime.now()
        
        report = {
            "training_report": {
                "timestamp": timestamp.isoformat(),
                "config": asdict(self.config),
                "models_trained": list(self.metrics.keys()),
                "best_model": self._get_best_model(),
                "model_comparison": self.metrics,
                "feature_importance": {},  # Would be populated from actual models
                "recommendations": []
            }
        }
        
        # Add recommendations based on results
        best_model = self._get_best_model()
        if best_model:
            best_r2 = best_model["metrics"].get("r2", 0)
            if best_r2 > 0.9:
                report["training_report"]["recommendations"].append("Excellent model performance - ready for production")
            elif best_r2 > 0.8:
                report["training_report"]["recommendations"].append("Good model performance - consider hyperparameter tuning")
            elif best_r2 > 0.6:
                report["training_report"]["recommendations"].append("Moderate performance - consider feature engineering")
            else:
                report["training_report"]["recommendations"].append("Poor performance - review data quality and features")
        
        return report
    
    def train_models(self):
        """Main training pipeline"""
        self.logger.info("🚀 Starting METR-LA ML training pipeline")
        
        try:
            # Load training data
            df = self.load_training_data()
            
            # Prepare features
            X, y = self.prepare_features(df)
            
            # Train models
            trained_models = self.train_sklearn_models(X, y)
            
            # Save models
            self.save_models(trained_models)
            
            # Generate report
            report = self.generate_training_report()
            
            self.logger.info("✅ ML training completed successfully!")
            
            # Print summary
            best_model = self._get_best_model()
            if best_model:
                self.logger.info(f"🏆 Best model: {best_model['model_name']}")
                self.logger.info(f"   R² Score: {best_model['metrics']['r2']:.3f}")
                self.logger.info(f"   RMSE: {best_model['metrics']['rmse']:.2f}")
            
            return trained_models, report
            
        except Exception as e:
            self.logger.error(f"Training failed: {e}", exc_info=True)
            raise
    
    def shutdown(self):
        """Cleanup resources"""
        if self.spark:
            self.spark.stop()

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='METR-LA ML Training Pipeline')
    parser.add_argument('--models', nargs='+', 
                       choices=['random_forest', 'gradient_boosting', 'xgboost', 'linear_regression', 'ridge'],
                       default=['random_forest', 'gradient_boosting', 'xgboost'],
                       help='Models to train')
    parser.add_argument('--test-size', type=float, default=0.2, help='Test set size')
    parser.add_argument('--target', default='avg_speed_mph', help='Target column')
    parser.add_argument('--output-dir', default='models', help='Output directory for models')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--quick-train', action='store_true', help='Use reduced parameters for quick training')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create configuration
    config = MLTrainingConfig(
        models=args.models,
        test_size=args.test_size,
        target_column=args.target,
        local_models_path=args.output_dir
    )
    
    # Initialize trainer
    trainer = MetrLAMLTrainer(config)
    
    try:
        print("🚀 Starting METR-LA ML Training Pipeline")
        print(f"📊 Models: {', '.join(args.models)}")
        print(f"🎯 Target: {args.target}")
        print(f"📁 Output: {args.output_dir}")
        print("=" * 60)
        
        # Train models
        trained_models, report = trainer.train_models()
        
        print("\n📈 Training Results:")
        for model_name, metrics in trainer.metrics.items():
            print(f"  {model_name:20}: R²={metrics['r2']:.3f}, RMSE={metrics['rmse']:.2f}")
        
        best_model = trainer._get_best_model()
        if best_model:
            print(f"\n🏆 Best Model: {best_model['model_name']} (R²={best_model['metrics']['r2']:.3f})")
        
        print(f"\n✅ Training completed! Models saved to: {args.output_dir}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Training cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=args.verbose)
        return 1
    finally:
        trainer.shutdown()

if __name__ == "__main__":
    exit(main())