#!/usr/bin/env python3
"""
METR-LA Real-time Prediction Service
Provides real-time traffic predictions using trained ML models
Consumes from Kafka, makes predictions, and publishes results
"""

import os
import sys
import json
import logging
import pickle
import asyncio
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

# Kafka imports
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

logger = logging.getLogger("metr_la_prediction")

@dataclass
class PredictionServiceConfig:
    """Configuration for METR-LA prediction service"""
    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:9093"
    input_topic: str = "processed-traffic-aggregates"
    output_topic: str = "traffic-predictions"
    consumer_group_id: str = "metr-la-prediction-service"
    
    # Model Configuration
    models_path: str = "models"
    primary_model: str = "gradient_boosting"  # Best performing model
    fallback_model: str = "random_forest"
    model_refresh_interval_minutes: int = 60  # Reload models every hour
    
    # Prediction Configuration
    prediction_horizons: Optional[List[int]] = None  # Minutes into future [15, 30, 60]
    confidence_threshold: float = 0.8
    max_prediction_age_minutes: int = 5
    
    # Service Configuration
    batch_size: int = 100
    processing_timeout_seconds: int = 30
    max_retries: int = 3
    
    # Output Configuration
    enable_kafka_output: bool = True
    enable_console_output: bool = True
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Set defaults for mutable fields"""
        if self.prediction_horizons is None:
            self.prediction_horizons = [15, 30, 60]  # 15min, 30min, 1hour

class MetrLAPredictionService:
    """Real-time prediction service for METR-LA traffic data"""
    
    def __init__(self, config: PredictionServiceConfig):
        """Initialize prediction service"""
        self.config = config
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.model_metadata: Dict[str, Dict[str, Any]] = {}
        self.consumer: Optional[KafkaConsumer] = None
        self.producer: Optional[KafkaProducer] = None
        self.running = False
        self.logger = self._setup_logging()
        
        # Statistics
        self.stats = {
            "messages_processed": 0,
            "predictions_made": 0,
            "errors": 0,
            "start_time": datetime.now(),
            "last_model_load": None
        }
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("metr_la_prediction")
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def load_models(self) -> bool:
        """Load trained ML models and scalers"""
        self.logger.info(f"Loading models from: {self.config.models_path}")
        
        models_dir = Path(self.config.models_path)
        if not models_dir.exists():
            self.logger.error(f"Models directory not found: {models_dir}")
            return False
        
        try:
            # Find latest model files
            model_files = {}
            scaler_files = []
            metadata_files = {}
            
            for file_path in models_dir.glob("*.pkl"):
                filename = file_path.stem
                
                if "scaler" in filename:
                    scaler_files.append(file_path)
                else:
                    # Extract model name and timestamp
                    parts = filename.split("_")
                    if len(parts) >= 2:
                        model_name = "_".join(parts[:-1])  # Everything except timestamp
                        timestamp = parts[-1]
                        
                        if model_name not in model_files or timestamp > model_files[model_name][1]:
                            model_files[model_name] = (file_path, timestamp)
            
            # Find corresponding metadata files
            for file_path in models_dir.glob("*_metadata.json"):
                filename = file_path.stem
                # Remove _metadata suffix
                model_timestamp = filename.replace("_metadata", "")
                
                # Extract model name
                parts = model_timestamp.split("_")
                if len(parts) >= 2:
                    model_name = "_".join(parts[:-1])
                    timestamp = parts[-1]
                    metadata_files[model_name] = file_path
            
            # Load models
            models_loaded = 0
            for model_name, (model_path, timestamp) in model_files.items():
                try:
                    self.logger.info(f"Loading {model_name} from {model_path}")
                    
                    with open(model_path, 'rb') as f:
                        model = pickle.load(f)
                    
                    self.models[model_name] = model
                    
                    # Load metadata if available
                    if model_name in metadata_files:
                        with open(metadata_files[model_name], 'r') as f:
                            metadata = json.load(f)
                        self.model_metadata[model_name] = metadata
                        
                        # Log model performance
                        metrics = metadata.get("metrics", {})
                        r2 = metrics.get("r2", "unknown")
                        rmse = metrics.get("rmse", "unknown")
                        self.logger.info(f"  {model_name}: R²={r2}, RMSE={rmse}")
                    
                    models_loaded += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to load {model_name}: {e}")
            
            # Load scalers
            scalers_loaded = 0
            if scaler_files:
                # Use the most recent scaler file
                latest_scaler = max(scaler_files, key=lambda p: p.stat().st_mtime)
                
                try:
                    self.logger.info(f"Loading scalers from {latest_scaler}")
                    
                    with open(latest_scaler, 'rb') as f:
                        scalers = pickle.load(f)
                    
                    self.scalers = scalers
                    scalers_loaded = len(scalers)
                    
                except Exception as e:
                    self.logger.error(f"Failed to load scalers: {e}")
            
            self.stats["last_model_load"] = datetime.now()
            
            self.logger.info(f"✅ Loaded {models_loaded} models and {scalers_loaded} scalers")
            
            # Verify primary and fallback models are available
            if self.config.primary_model not in self.models:
                self.logger.warning(f"Primary model '{self.config.primary_model}' not found")
                if self.models:
                    self.config.primary_model = list(self.models.keys())[0]
                    self.logger.info(f"Using '{self.config.primary_model}' as primary model")
            
            if self.config.fallback_model not in self.models:
                self.logger.warning(f"Fallback model '{self.config.fallback_model}' not found")
                if len(self.models) > 1:
                    fallback_options = [name for name in self.models.keys() 
                                     if name != self.config.primary_model]
                    if fallback_options:
                        self.config.fallback_model = fallback_options[0]
                        self.logger.info(f"Using '{self.config.fallback_model}' as fallback model")
            
            return models_loaded > 0
            
        except Exception as e:
            self.logger.error(f"Failed to load models: {e}")
            return False
    
    def initialize_kafka(self) -> bool:
        """Initialize Kafka consumer and producer"""
        self.logger.info("Initializing Kafka connections...")
        
        try:
            # Initialize consumer
            self.consumer = KafkaConsumer(
                self.config.input_topic,
                bootstrap_servers=self.config.kafka_bootstrap_servers,
                group_id=self.config.consumer_group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                consumer_timeout_ms=1000  # 1 second timeout for polling
            )
            
            # Initialize producer
            if self.config.enable_kafka_output:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.config.kafka_bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                    acks='all',
                    retries=self.config.max_retries,
                    batch_size=16384,
                    linger_ms=10
                )
            
            self.logger.info("✅ Kafka connections initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka: {e}")
            return False
    
    def prepare_features(self, data: Dict[str, Any]) -> Optional[np.ndarray]:
        """Prepare features from incoming traffic data for prediction"""
        try:
            # Expected feature columns (from training)
            feature_columns = [
                "avg_speed_kmh", "avg_volume_vph", "total_volume", "congestion_ratio",
                "speed_variability", "avg_traffic_efficiency", "hour_of_day", 
                "day_of_week", "is_weekend", "is_rush_hour", "avg_latitude", 
                "avg_longitude", "total_count", "avg_quality_score"
            ]
            
            # Extract features
            features = []
            for column in feature_columns:
                if column in data:
                    value = data[column]
                    # Handle boolean values
                    if isinstance(value, bool):
                        features.append(1.0 if value else 0.0)
                    else:
                        features.append(float(value) if value is not None else 0.0)
                else:
                    # Use default values for missing features
                    defaults = {
                        "avg_speed_kmh": 50.0,
                        "avg_volume_vph": 500.0,
                        "total_volume": 1000.0,
                        "congestion_ratio": 0.5,
                        "speed_variability": 0.2,
                        "avg_traffic_efficiency": 1.0,
                        "hour_of_day": 12.0,
                        "day_of_week": 3.0,
                        "is_weekend": 0.0,
                        "is_rush_hour": 0.0,
                        "avg_latitude": 34.0522,
                        "avg_longitude": -118.2437,
                        "total_count": 10.0,
                        "avg_quality_score": 0.8
                    }
                    features.append(defaults.get(column, 0.0))
            
            return np.array(features).reshape(1, -1)
            
        except Exception as e:
            self.logger.error(f"Failed to prepare features: {e}")
            return None
    
    def make_prediction(self, features: np.ndarray, model_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Make traffic prediction using specified model"""
        try:
            # Use primary model if not specified
            if model_name is None:
                model_name = self.config.primary_model
            
            # Check if model exists
            if model_name not in self.models:
                if self.config.fallback_model in self.models:
                    self.logger.warning(f"Model '{model_name}' not found, using fallback '{self.config.fallback_model}'")
                    model_name = self.config.fallback_model
                else:
                    self.logger.error(f"No suitable model found for prediction")
                    return None
            
            model = self.models[model_name]
            
            # Make prediction
            prediction = model.predict(features)[0]
            
            # Calculate confidence (simplified approach)
            # In production, this could use prediction intervals or ensemble variance
            base_confidence = 0.85
            
            # Adjust confidence based on model metadata
            if model_name in self.model_metadata:
                metrics = self.model_metadata[model_name].get("metrics", {})
                r2_score = metrics.get("r2", 0.8)
                base_confidence = min(0.95, base_confidence * (0.5 + 0.5 * r2_score))
            
            confidence = float(base_confidence)
            
            # Create prediction result
            result = {
                "predicted_speed_mph": float(prediction),
                "predicted_speed_kmh": float(prediction * 1.60934),
                "confidence": confidence,
                "model_used": model_name,
                "prediction_timestamp": datetime.now().isoformat(),
                "is_reliable": confidence >= self.config.confidence_threshold
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to make prediction with {model_name}: {e}")
            return None
    
    def create_multi_horizon_predictions(self, base_data: Dict[str, Any], base_prediction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create predictions for multiple time horizons"""
        predictions = []
        
        base_speed = base_prediction["predicted_speed_mph"]
        
        horizons = self.config.prediction_horizons or [15, 30, 60]
        for horizon_minutes in horizons:
            # Simple approach: adjust prediction based on time horizon
            # In production, this would use time-series models or trend analysis
            
            # Assume some degradation in accuracy over time
            time_decay = 1.0 - (horizon_minutes / 120.0) * 0.1  # 10% decay over 2 hours
            confidence_decay = max(0.5, base_prediction["confidence"] * time_decay)
            
            # Simple trend adjustment (could be much more sophisticated)
            trend_factor = 1.0
            if base_data.get("congestion_ratio", 0) > 0.7:
                # High congestion - expect some improvement over time
                trend_factor = 1.0 + (horizon_minutes / 60.0) * 0.05
            elif base_data.get("is_rush_hour", False):
                # Rush hour - expect worsening conditions
                trend_factor = 1.0 - (horizon_minutes / 60.0) * 0.03
            
            adjusted_speed = base_speed * trend_factor
            
            prediction = {
                "sensor_id": base_data.get("sensor_id", "unknown"),
                "segment_id": base_data.get("segment_id", "unknown"),
                "prediction_horizon_minutes": horizon_minutes,
                "predicted_speed_mph": float(adjusted_speed),
                "predicted_speed_kmh": float(adjusted_speed * 1.60934),
                "confidence": float(confidence_decay),
                "model_used": base_prediction["model_used"],
                "prediction_timestamp": datetime.now().isoformat(),
                "valid_until": (datetime.now() + timedelta(minutes=self.config.max_prediction_age_minutes)).isoformat(),
                "is_reliable": confidence_decay >= self.config.confidence_threshold,
                "base_data": {
                    "current_speed_mph": base_data.get("avg_speed_mph"),
                    "congestion_ratio": base_data.get("congestion_ratio"),
                    "volume": base_data.get("avg_volume_vph"),
                    "timestamp": base_data.get("window_start")
                }
            }
            
            predictions.append(prediction)
        
        return predictions
    
    def publish_predictions(self, predictions: List[Dict[str, Any]]):
        """Publish predictions to Kafka topic"""
        if not self.config.enable_kafka_output or not self.producer:
            return
        
        try:
            for prediction in predictions:
                # Use sensor_id as key for partitioning
                key = prediction.get("sensor_id", "unknown").encode('utf-8')
                
                # Send to Kafka
                future = self.producer.send(
                    self.config.output_topic,
                    key=key,
                    value=prediction
                )
                
                # Optionally wait for confirmation (for critical applications)
                # future.get(timeout=1)
            
            # Flush producer to ensure messages are sent
            self.producer.flush(timeout=1)
            
            self.stats["predictions_made"] += len(predictions)
            
        except KafkaError as e:
            self.logger.error(f"Failed to publish predictions to Kafka: {e}")
            self.stats["errors"] += 1
        except Exception as e:
            self.logger.error(f"Error publishing predictions: {e}")
            self.stats["errors"] += 1
    
    def process_message(self, message_data: Dict[str, Any]) -> bool:
        """Process a single traffic aggregate message"""
        try:
            # Prepare features
            features = self.prepare_features(message_data)
            if features is None:
                return False
            
            # Make base prediction
            base_prediction = self.make_prediction(features)
            if base_prediction is None:
                return False
            
            # Create multi-horizon predictions
            predictions = self.create_multi_horizon_predictions(message_data, base_prediction)
            
            # Publish predictions
            self.publish_predictions(predictions)
            
            # Console output
            if self.config.enable_console_output:
                sensor_id = message_data.get("sensor_id", "unknown")
                current_speed = message_data.get("avg_speed_mph", "unknown")
                predicted_speed = base_prediction["predicted_speed_mph"]
                confidence = base_prediction["confidence"]
                
                self.logger.info(f"Prediction: {sensor_id} | Current: {current_speed:.1f} mph | "
                               f"Predicted: {predicted_speed:.1f} mph | Confidence: {confidence:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process message: {e}")
            return False
    
    def print_stats(self):
        """Print service statistics"""
        uptime = datetime.now() - self.stats["start_time"]
        
        self.logger.info("📊 Prediction Service Statistics:")
        self.logger.info(f"   Uptime: {uptime}")
        self.logger.info(f"   Messages Processed: {self.stats['messages_processed']}")
        self.logger.info(f"   Predictions Made: {self.stats['predictions_made']}")
        self.logger.info(f"   Errors: {self.stats['errors']}")
        if self.stats["last_model_load"]:
            self.logger.info(f"   Last Model Load: {self.stats['last_model_load']}")
        self.logger.info(f"   Models Loaded: {list(self.models.keys())}")
    
    def run(self):
        """Main service loop"""
        self.logger.info("STARTING METR-LA Prediction Service")
        
        try:
            # Load models
            if not self.load_models():
                self.logger.error("Failed to load models, exiting")
                return False
            
            # Initialize Kafka
            if not self.initialize_kafka():
                self.logger.error("Failed to initialize Kafka, exiting")
                return False
            
            self.logger.info(f"📡 Consuming from topic: {self.config.input_topic}")
            self.logger.info(f"📤 Publishing to topic: {self.config.output_topic}")
            self.logger.info(f"🧠 Primary model: {self.config.primary_model}")
            self.logger.info(f"⏱️  Prediction horizons: {self.config.prediction_horizons} minutes")
            
            self.running = True
            last_stats_time = datetime.now()
            
            # Main processing loop
            while self.running:
                try:
                    # Poll for messages
                    if self.consumer is None:
                        break
                    message_batch = self.consumer.poll(timeout_ms=1000)
                    
                    if message_batch:
                        for topic_partition, messages in message_batch.items():
                            for message in messages:
                                if not self.running:
                                    break
                                
                                # Process message
                                success = self.process_message(message.value)
                                self.stats["messages_processed"] += 1
                                
                                if not success:
                                    self.stats["errors"] += 1
                    
                    # Print stats periodically
                    if datetime.now() - last_stats_time > timedelta(minutes=5):
                        self.print_stats()
                        last_stats_time = datetime.now()
                    
                    # Check if models need refreshing
                    if (self.stats["last_model_load"] and 
                        datetime.now() - self.stats["last_model_load"] > 
                        timedelta(minutes=self.config.model_refresh_interval_minutes)):
                        self.logger.info("Refreshing models...")
                        self.load_models()
                
                except KeyboardInterrupt:
                    self.logger.info("Received keyboard interrupt")
                    break
                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}")
                    self.stats["errors"] += 1
            
            self.logger.info("✅ METR-LA Prediction Service completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Service failed: {e}", exc_info=True)
            return False
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Shutdown service and cleanup resources"""
        self.logger.info("Shutting down prediction service...")
        
        try:
            if self.consumer:
                self.consumer.close()
            
            if self.producer:
                self.producer.close()
            
            # Print final stats
            self.print_stats()
            
            self.logger.info("Prediction service shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='METR-LA Real-time Prediction Service')
    parser.add_argument('--kafka-broker', default='localhost:9093', help='Kafka broker address')
    parser.add_argument('--input-topic', default='processed-traffic-aggregates', help='Input Kafka topic')
    parser.add_argument('--output-topic', default='traffic-predictions', help='Output Kafka topic')
    parser.add_argument('--models-path', default='models', help='Path to trained models')
    parser.add_argument('--primary-model', default='gradient_boosting', help='Primary model to use')
    parser.add_argument('--consumer-group', default='metr-la-prediction-service', help='Consumer group ID')
    parser.add_argument('--horizons', nargs='+', type=int, default=[15, 30, 60], 
                       help='Prediction horizons in minutes')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Log level')
    parser.add_argument('--disable-kafka-output', action='store_true', help='Disable Kafka output')
    parser.add_argument('--disable-console-output', action='store_true', help='Disable console output')
    parser.add_argument('--test-mode', action='store_true', help='Run in test mode')
    parser.add_argument('--duration', type=int, help='Duration to run in test mode (seconds)')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create configuration
    config = PredictionServiceConfig(
        kafka_bootstrap_servers=args.kafka_broker,
        input_topic=args.input_topic,
        output_topic=args.output_topic,
        models_path=args.models_path,
        primary_model=args.primary_model,
        consumer_group_id=args.consumer_group,
        prediction_horizons=args.horizons,
        enable_kafka_output=not args.disable_kafka_output,
        enable_console_output=not args.disable_console_output,
        log_level=args.log_level
    )
    
    # Initialize service
    service = MetrLAPredictionService(config)
    
    try:
        print("STARTING METR-LA Prediction Service")
        print(f"📡 Input Topic: {args.input_topic}")
        print(f"📤 Output Topic: {args.output_topic}")
        print(f"🧠 Primary Model: {args.primary_model}")
        print(f"⏱️  Horizons: {args.horizons} minutes")
        print("=" * 60)
        
        success = service.run()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Service interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Service failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())