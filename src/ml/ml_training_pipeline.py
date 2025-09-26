"""
Complete ML Training Pipeline

Main orchestrator that integrates all ML training components:
- Data loading and preprocessing
- Model training with multiple algorithms
- Model evaluation and comparison
- Model persistence and versioning
"""

import os
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path

import pandas as pd
import numpy as np

# Import our ML components
from config_manager import MLTrainingConfigManager, get_ml_config_manager
from data_loader import DataLoader
from model_trainer import ModelTrainer, TrainedModel
from model_evaluator import ModelEvaluator
from model_persistence import ModelPersistenceManager

# Spark integration
from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)


class MLTrainingPipeline:
    """Complete ML training pipeline orchestrator"""
    
    def __init__(self, config_path: str = "config/ml_training_config.json",
                 spark_session: Optional[SparkSession] = None):
        """
        Initialize ML training pipeline
        
        Args:
            config_path: Path to ML training configuration
            spark_session: Optional Spark session
        """
        self.config = get_ml_config_manager(config_path)
        self.spark = spark_session or self._create_spark_session()
        
        # Initialize components
        self.data_loader = DataLoader(self.config, self.spark)
        self.model_trainer = ModelTrainer(self.config)
        self.model_evaluator = ModelEvaluator(self.config)
        self.model_persistence = ModelPersistenceManager(self.config, self.spark)
        
        # Pipeline state
        self.pipeline_id = f"ml_pipeline_{int(time.time())}"
        self.results = {}
        
        # Setup logging
        self._setup_logging()
        
        logger.info(f"ML Training Pipeline initialized with ID: {self.pipeline_id}")
    
    def _create_spark_session(self) -> SparkSession:
        """Create Spark session with configuration"""
        builder = SparkSession.builder.appName(self.config.spark_config.app_name)
        
        for key, value in self.config.spark_config.config.items():
            builder = builder.config(key, value)
        
        return builder.getOrCreate()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.logging
        
        # Create logs directory
        log_dir = Path(log_config.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_config.level),
            format=log_config.log_format,
            handlers=[
                logging.FileHandler(log_config.log_file_path),
                logging.StreamHandler()
            ]
        )
    
    def run_complete_pipeline(self, 
                            feature_path: Optional[str] = None,
                            output_dir: str = "ml_training_results") -> Dict[str, Any]:
        """
        Run the complete ML training pipeline
        
        Args:
            feature_path: Optional override for feature input path
            output_dir: Directory to save results
            
        Returns:
            Complete pipeline results
        """
        logger.info(f"Starting complete ML training pipeline: {self.pipeline_id}")
        start_time = datetime.now()
        
        try:
            # Step 1: Data Loading and Preparation
            logger.info("Step 1: Data Loading and Preparation")
            data_result = self._run_data_preparation(feature_path)
            
            # Step 2: Model Training
            logger.info("Step 2: Model Training")
            training_result = self._run_model_training(data_result)
            
            # Step 3: Model Evaluation
            logger.info("Step 3: Model Evaluation")  
            evaluation_result = self._run_model_evaluation(training_result, data_result, output_dir)
            
            # Step 4: Model Persistence
            logger.info("Step 4: Model Persistence")
            persistence_result = self._run_model_persistence(training_result, data_result)
            
            # Step 5: Generate Final Report
            logger.info("Step 5: Generating Final Report")
            final_report = self._generate_final_report(
                data_result, training_result, evaluation_result, 
                persistence_result, start_time, output_dir
            )
            
            # Complete pipeline results
            pipeline_results = {
                "pipeline_id": self.pipeline_id,
                "status": "completed",
                "data_preparation": data_result,
                "model_training": training_result,
                "model_evaluation": evaluation_result,
                "model_persistence": persistence_result,
                "final_report": final_report,
                "pipeline_duration": (datetime.now() - start_time).total_seconds(),
                "output_directory": output_dir
            }
            
            # Save complete results
            self._save_pipeline_results(pipeline_results, output_dir)
            
            logger.info(f"ML training pipeline completed successfully: {self.pipeline_id}")
            return pipeline_results
            
        except Exception as e:
            logger.error(f"ML training pipeline failed: {str(e)}")
            
            error_result = {
                "pipeline_id": self.pipeline_id,
                "status": "failed",
                "error": str(e),
                "pipeline_duration": (datetime.now() - start_time).total_seconds()
            }
            
            return error_result
    
    def _run_data_preparation(self, feature_path: Optional[str] = None) -> Dict[str, Any]:
        """Run data loading and preparation step"""
        logger.info("Loading and preparing data...")
        
        try:
            # Load complete data pipeline
            data_result = self.data_loader.load_data_complete_pipeline(
                feature_path=feature_path,
                convert_to_pandas=True
            )
            
            # Save preprocessing artifacts
            preprocessing_dir = "preprocessing_artifacts"
            os.makedirs(preprocessing_dir, exist_ok=True)
            self.data_loader.save_preprocessor_artifacts(preprocessing_dir)
            
            logger.info(f"Data preparation completed successfully")
            logger.info(f"Training samples: {data_result['metadata']['train_samples']}")
            logger.info(f"Validation samples: {data_result['metadata']['val_samples']}")
            logger.info(f"Test samples: {data_result['metadata']['test_samples']}")
            logger.info(f"Feature columns: {len(data_result['metadata']['feature_columns'])}")
            
            return {
                "status": "completed",
                "data": data_result,
                "preprocessing_artifacts_dir": preprocessing_dir
            }
            
        except Exception as e:
            logger.error(f"Data preparation failed: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _run_model_training(self, data_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run model training step"""
        logger.info("Training models...")
        
        if data_result["status"] != "completed":
            return {"status": "skipped", "reason": "Data preparation failed"}
        
        try:
            # Extract training data
            train_data = data_result["data"]["pandas_dataframes"]["train"]
            val_data = data_result["data"]["pandas_dataframes"]["validation"]
            
            X_train, y_train = train_data["X"], train_data["y"]
            X_val, y_val = val_data["X"], val_data["y"]
            
            # Train all enabled models
            trained_models = self.model_trainer.train_all_models(
                X_train, y_train, X_val, y_val
            )
            
            # Create ensemble models if enabled
            if self.config.model_selection.ensemble_models and len(trained_models) > 1:
                logger.info("Creating ensemble models...")
                ensemble_models = self.model_trainer.create_ensemble_models(
                    trained_models, X_train, y_train, X_val, y_val
                )
                trained_models.update(ensemble_models)
            
            # Select best model
            if trained_models:
                best_model_name, best_model = self.model_trainer.select_best_model(trained_models)
                logger.info(f"Best model selected: {best_model_name}")
            else:
                best_model_name, best_model = None, None
                logger.warning("No models were successfully trained")
            
            # Training summary
            training_summary = self.model_trainer.get_training_summary()
            
            logger.info(f"Model training completed: {len(trained_models)} models trained")
            
            return {
                "status": "completed",
                "trained_models": trained_models,
                "best_model": {"name": best_model_name, "model": best_model},
                "training_summary": training_summary
            }
            
        except Exception as e:
            logger.error(f"Model training failed: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _run_model_evaluation(self, training_result: Dict[str, Any],
                            data_result: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
        """Run model evaluation step"""
        logger.info("Evaluating models...")
        
        if training_result["status"] != "completed":
            return {"status": "skipped", "reason": "Model training failed"}
        
        try:
            # Extract test data
            test_data = data_result["data"]["pandas_dataframes"]["test"]
            X_test, y_test = test_data["X"], test_data["y"]
            
            # Evaluate all models
            trained_models = training_result["trained_models"]
            evaluation_dir = os.path.join(output_dir, "model_evaluation")
            
            evaluation_results = self.model_evaluator.evaluate_all_models(
                trained_models, X_test, y_test, evaluation_dir
            )
            
            logger.info(f"Model evaluation completed")
            logger.info(f"Evaluation results saved to: {evaluation_dir}")
            
            return {
                "status": "completed",  
                "evaluation_results": evaluation_results,
                "evaluation_directory": evaluation_dir
            }
            
        except Exception as e:
            logger.error(f"Model evaluation failed: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _run_model_persistence(self, training_result: Dict[str, Any],  
                             data_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run model persistence step"""
        logger.info("Persisting models...")
        
        if training_result["status"] != "completed":
            return {"status": "skipped", "reason": "Model training failed"}
        
        try:
            trained_models = training_result["trained_models"]
            feature_columns = data_result["data"]["metadata"]["feature_columns"]
            target_columns = data_result["data"]["metadata"]["target_columns"]
            
            # Create data schema
            data_schema = {
                "feature_columns": feature_columns,
                "target_columns": target_columns,
                "total_features": len(feature_columns),
                "data_types": "mixed"  # Would be more detailed in real implementation
            }
            
            # Save all trained models
            saved_models = {}
            for model_name, trained_model in trained_models.items():
                try:
                    version_id = self.model_persistence.save_trained_model(
                        trained_model=trained_model,
                        feature_columns=feature_columns,
                        target_columns=target_columns,
                        data_schema=data_schema,
                        description=f"Model trained in pipeline {self.pipeline_id}",
                        tags=["pipeline", self.pipeline_id, trained_model.model_type],
                        created_by="ml_pipeline"
                    )
                    
                    saved_models[model_name] = version_id
                    logger.info(f"Model {model_name} saved with version ID: {version_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to save model {model_name}: {str(e)}")
            
            # Get model registry status
            registry_status = self.model_persistence.get_model_registry_status()
            
            logger.info(f"Model persistence completed: {len(saved_models)} models saved")
            
            return {
                "status": "completed",
                "saved_models": saved_models,
                "registry_status": registry_status
            }
            
        except Exception as e:
            logger.error(f"Model persistence failed: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _generate_final_report(self, data_result: Dict[str, Any],
                             training_result: Dict[str, Any],
                             evaluation_result: Dict[str, Any],
                             persistence_result: Dict[str, Any],
                             start_time: datetime, output_dir: str) -> Dict[str, Any]:
        """Generate final pipeline report"""
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Extract key metrics
        best_model_info = training_result.get("best_model", {})
        best_model_name = best_model_info.get("name", "None")
        
        # Get best model metrics
        best_model_metrics = {}
        if best_model_name and best_model_name != "None":
            best_model_obj = best_model_info.get("model")
            if best_model_obj and hasattr(best_model_obj, 'metrics'):
                best_model_metrics = best_model_obj.metrics.to_dict()
        
        # Create summary report
        report = {
            "pipeline_summary": {
                "pipeline_id": self.pipeline_id,
                "execution_time_seconds": duration,
                "execution_time_formatted": f"{duration:.2f} seconds",
                "completed_at": datetime.now().isoformat(),
                "status": "completed"
            },
            "data_summary": {
                "total_samples": data_result["data"]["metadata"]["total_samples"] if data_result["status"] == "completed" else 0,
                "training_samples": data_result["data"]["metadata"]["train_samples"] if data_result["status"] == "completed" else 0,
                "validation_samples": data_result["data"]["metadata"]["val_samples"] if data_result["status"] == "completed" else 0,
                "test_samples": data_result["data"]["metadata"]["test_samples"] if data_result["status"] == "completed" else 0,
                "feature_count": len(data_result["data"]["metadata"]["feature_columns"]) if data_result["status"] == "completed" else 0,
                "target_columns": data_result["data"]["metadata"]["target_columns"] if data_result["status"] == "completed" else []
            },
            "training_summary": {
                "models_trained": len(training_result.get("trained_models", {})),
                "best_model": best_model_name,
                "best_model_metrics": best_model_metrics,
                "ensemble_models_created": self.config.model_selection.ensemble_models
            },
            "evaluation_summary": {
                "evaluation_completed": evaluation_result["status"] == "completed",
                "evaluation_directory": evaluation_result.get("evaluation_directory", ""),
                "plots_generated": bool(evaluation_result.get("evaluation_results", {}).get("generated_plots", {}))
            },
            "persistence_summary": {
                "models_saved": len(persistence_result.get("saved_models", {})),
                "registry_status": persistence_result.get("registry_status", {})
            },
            "configuration": {
                "enabled_models": list(self.config.get_enabled_models().keys()),
                "primary_metric": self.config.model_selection.primary_metric,
                "cross_validation_enabled": self.config.training.cross_validation.enabled,
                "hyperparameter_tuning_enabled": any(
                    model.hyperparameter_tuning for model in self.config.models.values()
                )
            }
        }
        
        # Generate text report
        text_report = self._generate_text_report(report)
        
        # Save report
        report_path = os.path.join(output_dir, "pipeline_final_report.json")
        text_report_path = os.path.join(output_dir, "pipeline_final_report.txt")
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        with open(text_report_path, 'w') as f:
            f.write(text_report)
        
        report["report_files"] = {
            "json": report_path,
            "text": text_report_path
        }
        
        return report
    
    def _generate_text_report(self, report: Dict[str, Any]) -> str:
        """Generate human-readable text report"""
        
        lines = [
            "=" * 80,
            "ML TRAINING PIPELINE FINAL REPORT",
            "=" * 80,
            f"Pipeline ID: {report['pipeline_summary']['pipeline_id']}",
            f"Completed at: {report['pipeline_summary']['completed_at']}",
            f"Execution time: {report['pipeline_summary']['execution_time_formatted']}",
            f"Status: {report['pipeline_summary']['status']}",
            "",
            "DATA SUMMARY:",
            f"  Total samples: {report['data_summary']['total_samples']:,}",
            f"  Training samples: {report['data_summary']['training_samples']:,}",
            f"  Validation samples: {report['data_summary']['validation_samples']:,}",
            f"  Test samples: {report['data_summary']['test_samples']:,}",
            f"  Feature count: {report['data_summary']['feature_count']}",
            f"  Target columns: {', '.join(report['data_summary']['target_columns'])}",
            "",
            "TRAINING SUMMARY:",
            f"  Models trained: {report['training_summary']['models_trained']}",
            f"  Best model: {report['training_summary']['best_model']}",
            f"  Ensemble models: {report['training_summary']['ensemble_models_created']}",
            ""
        ]
        
        # Best model metrics
        if report['training_summary']['best_model_metrics']:
            lines.append("  Best model metrics:")
            for metric, value in report['training_summary']['best_model_metrics'].items():
                if isinstance(value, (int, float)) and value is not None:
                    lines.append(f"    {metric}: {value:.4f}")
            lines.append("")
        
        lines.extend([
            "EVALUATION SUMMARY:",
            f"  Evaluation completed: {report['evaluation_summary']['evaluation_completed']}",
            f"  Plots generated: {report['evaluation_summary']['plots_generated']}",
            f"  Evaluation directory: {report['evaluation_summary']['evaluation_directory']}",
            "",
            "PERSISTENCE SUMMARY:",
            f"  Models saved: {report['persistence_summary']['models_saved']}",
            f"  Total models in registry: {report['persistence_summary']['registry_status'].get('total_models', 0)}",
            f"  Total versions in registry: {report['persistence_summary']['registry_status'].get('total_versions', 0)}",
            "",
            "CONFIGURATION:",
            f"  Enabled models: {', '.join(report['configuration']['enabled_models'])}",
            f"  Primary metric: {report['configuration']['primary_metric']}",
            f"  Cross-validation: {report['configuration']['cross_validation_enabled']}",
            f"  Hyperparameter tuning: {report['configuration']['hyperparameter_tuning_enabled']}",
            "",
            "=" * 80
        ])
        
        return "\n".join(lines)
    
    def _save_pipeline_results(self, results: Dict[str, Any], output_dir: str):
        """Save complete pipeline results"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Save main results (without large objects)
        results_copy = results.copy()
        
        # Remove large objects that can't be serialized
        if "data_preparation" in results_copy and "data" in results_copy["data_preparation"]:
            # Keep only metadata
            results_copy["data_preparation"]["data"] = {
                "metadata": results_copy["data_preparation"]["data"]["metadata"]
            }
        
        if "model_training" in results_copy and "trained_models" in results_copy["model_training"]:
            # Keep only model summaries
            model_summaries = {}
            for name, model in results_copy["model_training"]["trained_models"].items():
                if hasattr(model, 'to_dict'):
                    model_summaries[name] = model.to_dict()
                else:
                    model_summaries[name] = {"model_name": name}
            results_copy["model_training"]["trained_models"] = model_summaries
        
        results_path = os.path.join(output_dir, "complete_pipeline_results.json")
        with open(results_path, 'w') as f:
            json.dump(self._convert_for_json(results_copy), f, indent=2)
        
        logger.info(f"Pipeline results saved to: {results_path}")
    
    def _convert_for_json(self, obj: Any) -> Any:
        """Convert objects for JSON serialization"""
        if isinstance(obj, dict):
            return {key: self._convert_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_for_json(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif pd.isna(obj):
            return None
        else:
            return obj
    
    def run_inference_pipeline(self, model_name: str, features: pd.DataFrame,
                             version: Optional[str] = None) -> Dict[str, Any]:
        """
        Run inference with a trained model
        
        Args:
            model_name: Name of the model to use
            features: Features for prediction
            version: Model version (latest if not specified)
            
        Returns:
            Prediction results
        """
        logger.info(f"Running inference with model: {model_name}")
        
        try:
            # Load model
            model, metadata = self.model_persistence.load_model(model_name, version)
            
            # Make predictions
            predictions = model.predict(features)
            
            # Prepare results
            results = {
                "model_name": model_name,
                "model_version": version or "latest",
                "predictions": predictions.tolist() if hasattr(predictions, 'tolist') else predictions,
                "num_predictions": len(predictions),
                "features_used": features.columns.tolist(),
                "inference_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Inference completed: {len(predictions)} predictions made")
            return results
            
        except Exception as e:
            logger.error(f"Inference failed: {str(e)}")
            return {"error": str(e)}
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'data_loader'):
            self.data_loader.close()
        
        if hasattr(self, 'spark'):
            self.spark.stop()
        
        logger.info("ML Training Pipeline cleanup completed")


def main():
    """Main execution function for running the complete pipeline"""
    
    # Initialize pipeline
    pipeline = MLTrainingPipeline()
    
    try:
        # Run complete pipeline
        results = pipeline.run_complete_pipeline(
            output_dir="ml_training_results"
        )
        
        print("\n" + "="*80)
        print("ML TRAINING PIPELINE COMPLETED")
        print("="*80)
        print(f"Pipeline ID: {results.get('pipeline_id', 'unknown')}")
        print(f"Status: {results.get('status', 'unknown')}")
        print(f"Duration: {results.get('pipeline_duration', 0):.2f} seconds")
        
        if results.get('status') == 'completed':
            print(f"Results saved to: {results.get('output_directory', 'unknown')}")
            
            # Show best model info
            training_result = results.get('model_training', {})
            best_model = training_result.get('best_model', {})
            if best_model.get('name'):
                print(f"Best model: {best_model['name']}")
        else:
            print(f"Error: {results.get('error', 'unknown')}")
        
        print("="*80)
        
    finally:
        # Cleanup
        pipeline.cleanup()


if __name__ == "__main__":
    main()