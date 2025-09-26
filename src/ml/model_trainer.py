"""
Model Training Framework

Comprehensive ML model training framework supporting multiple algorithms
with hyperparameter tuning, cross-validation, and parallel training.
"""

import os
import logging
import time
import warnings
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass, asdict
import json
import pickle
import joblib
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd

# Scikit-learn models and utilities
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor, StackingRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import (
    GridSearchCV, RandomizedSearchCV, cross_val_score, 
    validation_curve, learning_curve, TimeSeriesSplit
)
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score, 
    max_error, mean_squared_log_error
)
from sklearn.base import BaseEstimator, RegressorMixin

# XGBoost (if available)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    xgb = None

# LightGBM (if available)
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    lgb = None

# Import configuration
from config_manager import MLTrainingConfigManager, get_ml_config_manager

warnings.filterwarnings('ignore', category=UserWarning)
logger = logging.getLogger(__name__)


@dataclass
class ModelMetrics:
    """Container for model performance metrics"""
    rmse: float
    mae: float
    mape: float
    r2_score: float
    max_error: float
    mean_squared_log_error: Optional[float]
    training_time: float
    prediction_time: float
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return asdict(self)
    
    def get_composite_score(self, weights: Dict[str, float]) -> float:
        """Calculate composite score based on weights"""
        metrics_dict = self.to_dict()
        score = 0.0
        
        for metric_name, weight in weights.items():
            if metric_name in metrics_dict and metrics_dict[metric_name] is not None:
                # For metrics where lower is better (RMSE, MAE, MAPE, max_error)
                if metric_name in ['rmse', 'mae', 'mape', 'max_error', 'training_time']:
                    score += weight * (1.0 / (1.0 + metrics_dict[metric_name]))
                # For metrics where higher is better (R2)
                elif metric_name == 'r2_score':
                    score += weight * max(0.0, metrics_dict[metric_name])
        
        return score


@dataclass
class TrainedModel:
    """Container for trained model and its metadata"""
    model: BaseEstimator
    model_name: str
    model_type: str
    hyperparameters: Dict[str, Any]
    metrics: ModelMetrics
    feature_importance: Optional[Dict[str, float]]
    training_metadata: Dict[str, Any]
    trained_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding the actual model object)"""
        return {
            "model_name": self.model_name,
            "model_type": self.model_type,
            "hyperparameters": self.hyperparameters,
            "metrics": self.metrics.to_dict(),
            "feature_importance": self.feature_importance,
            "training_metadata": self.training_metadata,
            "trained_at": self.trained_at.isoformat()
        }


class ModelFactory:
    """Factory for creating different types of models"""
    
    @staticmethod
    def create_model(model_type: str, hyperparameters: Dict[str, Any]) -> BaseEstimator:
        """
        Create model instance based on type and hyperparameters
        
        Args:
            model_type: Type of model to create
            hyperparameters: Model hyperparameters
            
        Returns:
            Model instance
        """
        if model_type == "linear_regression":
            return LinearRegression(**hyperparameters)
        
        elif model_type == "ridge":
            return Ridge(**hyperparameters)
        
        elif model_type == "lasso":
            return Lasso(**hyperparameters)
        
        elif model_type == "elastic_net":
            return ElasticNet(**hyperparameters)
        
        elif model_type == "random_forest":
            return RandomForestRegressor(**hyperparameters)
        
        elif model_type == "gradient_boosting":
            return GradientBoostingRegressor(**hyperparameters)
        
        elif model_type == "support_vector_regression":
            return SVR(**hyperparameters)
        
        elif model_type == "mlp":
            return MLPRegressor(**hyperparameters)
        
        elif model_type == "xgboost" and XGBOOST_AVAILABLE:
            return xgb.XGBRegressor(**hyperparameters)
        
        elif model_type == "lightgbm" and LIGHTGBM_AVAILABLE:
            return lgb.LGBMRegressor(**hyperparameters)
        
        else:
            raise ValueError(f"Unsupported model type: {model_type}")


class HyperparameterTuner:
    """Handles hyperparameter tuning for models"""
    
    def __init__(self, config: MLTrainingConfigManager):
        self.config = config
    
    def tune_hyperparameters(self, 
                           model_type: str,
                           base_model: BaseEstimator,
                           param_grid: Dict[str, List[Any]],
                           X_train: pd.DataFrame,
                           y_train: pd.DataFrame,
                           X_val: pd.DataFrame,
                           y_val: pd.DataFrame) -> Tuple[BaseEstimator, Dict[str, Any]]:
        """
        Tune hyperparameters for a model
        
        Args:
            model_type: Type of model
            base_model: Base model instance
            param_grid: Parameter grid for tuning
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            
        Returns:
            Tuple of (best_model, best_params)
        """
        logger.info(f"Tuning hyperparameters for {model_type}")
        
        tuning_config = self.config.training.hyperparameter_tuning
        
        if tuning_config.method == "grid_search":
            search = GridSearchCV(
                estimator=base_model,
                param_grid=param_grid,
                cv=tuning_config.cv_folds,
                scoring=tuning_config.scoring,
                n_jobs=tuning_config.n_jobs,
                verbose=tuning_config.verbose
            )
        elif tuning_config.method == "random_search":
            search = RandomizedSearchCV(
                estimator=base_model,
                param_distributions=param_grid,
                n_iter=50,  # Could be configurable
                cv=tuning_config.cv_folds,
                scoring=tuning_config.scoring,
                n_jobs=tuning_config.n_jobs,
                verbose=tuning_config.verbose,
                random_state=42
            )
        else:
            raise ValueError(f"Unsupported tuning method: {tuning_config.method}")
        
        # Fit the search
        search.fit(X_train, y_train.iloc[:, 0] if len(y_train.columns) > 1 else y_train.squeeze())
        
        logger.info(f"Best parameters for {model_type}: {search.best_params_}")
        logger.info(f"Best CV score for {model_type}: {search.best_score_:.4f}")
        
        return search.best_estimator_, search.best_params_


class ModelTrainer:
    """Main model training orchestrator"""
    
    def __init__(self, config: MLTrainingConfigManager):
        """
        Initialize model trainer
        
        Args:
            config: ML training configuration
        """
        self.config = config
        self.model_factory = ModelFactory()
        self.hyperparameter_tuner = HyperparameterTuner(config)
        self.trained_models: Dict[str, TrainedModel] = {}
        
        logger.info("ModelTrainer initialized")
    
    def train_single_model(self,
                          model_type: str,
                          X_train: pd.DataFrame,
                          y_train: pd.DataFrame,
                          X_val: pd.DataFrame,
                          y_val: pd.DataFrame,
                          model_name: Optional[str] = None) -> TrainedModel:
        """
        Train a single model
        
        Args:
            model_type: Type of model to train
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            model_name: Optional custom model name
            
        Returns:
            Trained model container
        """
        model_name = model_name or f"{model_type}_{int(time.time())}"
        logger.info(f"Training model: {model_name} (type: {model_type})")
        
        # Get model configuration
        if model_type not in self.config.models:
            raise ValueError(f"Model type {model_type} not configured")
        
        model_config = self.config.models[model_type]
        if not model_config.enabled:
            logger.warning(f"Model type {model_type} is not enabled")
            return None
        
        # Create base model
        base_hyperparameters = model_config.params.copy()
        model = self.model_factory.create_model(model_type, base_hyperparameters)
        
        # Hyperparameter tuning if enabled
        best_params = base_hyperparameters.copy()
        if model_config.hyperparameter_tuning and model_config.param_grid:
            try:
                model, best_params = self.hyperparameter_tuner.tune_hyperparameters(
                    model_type, model, model_config.param_grid, 
                    X_train, y_train, X_val, y_val
                )
            except Exception as e:
                logger.warning(f"Hyperparameter tuning failed for {model_type}: {str(e)}")
                logger.info("Continuing with default parameters")
        
        # Train the model
        start_time = time.time()
        
        # Handle multi-target case
        if len(y_train.columns) == 1:
            y_train_fit = y_train.squeeze()
            y_val_fit = y_val.squeeze()
        else:
            y_train_fit = y_train
            y_val_fit = y_val
        
        model.fit(X_train, y_train_fit)
        training_time = time.time() - start_time
        
        # Make predictions for evaluation
        start_pred_time = time.time()
        y_pred = model.predict(X_val)
        prediction_time = time.time() - start_pred_time
        
        # Handle multi-target predictions
        if len(y_val.columns) == 1:
            y_val_eval = y_val.squeeze()
        else:
            y_val_eval = y_val.iloc[:, 0]  # Use first target for evaluation
        
        if len(y_pred.shape) > 1 and y_pred.shape[1] > 1:
            y_pred_eval = y_pred[:, 0]  # Use first target for evaluation
        else:
            y_pred_eval = y_pred
        
        # Calculate metrics
        metrics = self._calculate_metrics(y_val_eval, y_pred_eval, training_time, prediction_time)
        
        # Get feature importance if available
        feature_importance = self._get_feature_importance(model, X_train.columns.tolist())
        
        # Create training metadata
        training_metadata = {
            "training_samples": len(X_train),
            "validation_samples": len(X_val),
            "feature_count": len(X_train.columns),
            "target_columns": y_train.columns.tolist(),
            "hyperparameter_tuning": model_config.hyperparameter_tuning,
            "cross_validation": self.config.training.cross_validation.enabled
        }
        
        # Create trained model container
        trained_model = TrainedModel(
            model=model,
            model_name=model_name,
            model_type=model_type,
            hyperparameters=best_params,
            metrics=metrics,
            feature_importance=feature_importance,
            training_metadata=training_metadata,
            trained_at=datetime.now()
        )
        
        logger.info(f"Model {model_name} trained successfully")
        logger.info(f"Validation RMSE: {metrics.rmse:.4f}, MAE: {metrics.mae:.4f}, R2: {metrics.r2_score:.4f}")
        
        return trained_model
    
    def train_all_models(self,
                        X_train: pd.DataFrame,
                        y_train: pd.DataFrame,
                        X_val: pd.DataFrame,
                        y_val: pd.DataFrame) -> Dict[str, TrainedModel]:
        """
        Train all enabled models
        
        Args:
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            
        Returns:
            Dictionary of trained models
        """
        logger.info("Training all enabled models")
        
        enabled_models = self.config.get_enabled_models()
        
        if self.config.performance.parallel_training:
            return self._train_models_parallel(enabled_models, X_train, y_train, X_val, y_val)
        else:
            return self._train_models_sequential(enabled_models, X_train, y_train, X_val, y_val)
    
    def _train_models_sequential(self,
                               enabled_models: Dict[str, Any],
                               X_train: pd.DataFrame,
                               y_train: pd.DataFrame,
                               X_val: pd.DataFrame,
                               y_val: pd.DataFrame) -> Dict[str, TrainedModel]:
        """Train models sequentially"""
        trained_models = {}
        
        for model_type in enabled_models.keys():
            try:
                trained_model = self.train_single_model(
                    model_type, X_train, y_train, X_val, y_val
                )
                if trained_model:
                    trained_models[model_type] = trained_model
                    self.trained_models[model_type] = trained_model
            except Exception as e:
                logger.error(f"Failed to train {model_type}: {str(e)}")
        
        return trained_models
    
    def _train_models_parallel(self,
                             enabled_models: Dict[str, Any],
                             X_train: pd.DataFrame,
                             y_train: pd.DataFrame,
                             X_val: pd.DataFrame,
                             y_val: pd.DataFrame) -> Dict[str, TrainedModel]:
        """Train models in parallel"""
        trained_models = {}
        max_workers = min(self.config.performance.max_workers, len(enabled_models))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit training jobs
            future_to_model_type = {
                executor.submit(
                    self.train_single_model,
                    model_type, X_train, y_train, X_val, y_val
                ): model_type
                for model_type in enabled_models.keys()
            }
            
            # Collect results
            for future in as_completed(future_to_model_type):
                model_type = future_to_model_type[future]
                try:
                    trained_model = future.result()
                    if trained_model:
                        trained_models[model_type] = trained_model
                        self.trained_models[model_type] = trained_model
                        logger.info(f"Completed training {model_type}")
                except Exception as e:
                    logger.error(f"Failed to train {model_type}: {str(e)}")
        
        return trained_models
    
    def perform_cross_validation(self,
                               model_type: str,
                               X: pd.DataFrame,
                               y: pd.DataFrame) -> Dict[str, float]:
        """
        Perform cross-validation for a model type
        
        Args:
            model_type: Type of model
            X: Features
            y: Targets
            
        Returns:
            Cross-validation scores
        """
        logger.info(f"Performing cross-validation for {model_type}")
        
        if not self.config.training.cross_validation.enabled:
            logger.info("Cross-validation is disabled")
            return {}
        
        # Get model configuration
        model_config = self.config.models[model_type]
        model = self.model_factory.create_model(model_type, model_config.params)
        
        cv_config = self.config.training.cross_validation
        
        # Handle multi-target case
        if len(y.columns) == 1:
            y_cv = y.squeeze()
        else:
            y_cv = y.iloc[:, 0]  # Use first target for CV
        
        # Perform cross-validation
        if cv_config.shuffle:
            cv_scores = cross_val_score(
                model, X, y_cv,
                cv=cv_config.cv_folds,
                scoring=cv_config.scoring,
                n_jobs=-1
            )
        else:
            # Use TimeSeriesSplit for time series data
            tscv = TimeSeriesSplit(n_splits=cv_config.cv_folds)
            cv_scores = cross_val_score(
                model, X, y_cv,
                cv=tscv,
                scoring=cv_config.scoring,
                n_jobs=-1
            )
        
        cv_results = {
            "mean_score": cv_scores.mean(),
            "std_score": cv_scores.std(),
            "scores": cv_scores.tolist()
        }
        
        logger.info(f"CV results for {model_type}: {cv_results['mean_score']:.4f} ± {cv_results['std_score']:.4f}")
        
        return cv_results
    
    def create_ensemble_models(self,
                             trained_models: Dict[str, TrainedModel],
                             X_train: pd.DataFrame,
                             y_train: pd.DataFrame,
                             X_val: pd.DataFrame,
                             y_val: pd.DataFrame) -> Dict[str, TrainedModel]:
        """
        Create ensemble models from trained base models
        
        Args:
            trained_models: Dictionary of trained base models
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            
        Returns:
            Dictionary of ensemble models
        """
        if not self.config.model_selection.ensemble_models:
            return {}
        
        logger.info("Creating ensemble models")
        ensemble_models = {}
        
        if len(trained_models) < 2:
            logger.warning("Need at least 2 base models for ensemble")
            return {}
        
        # Get base models
        base_models = [(name, model.model) for name, model in trained_models.items()]
        
        # Handle multi-target case
        if len(y_train.columns) == 1:
            y_train_fit = y_train.squeeze()
            y_val_fit = y_val.squeeze()
        else:
            y_train_fit = y_train.iloc[:, 0]
            y_val_fit = y_val.iloc[:, 0]
        
        # Voting ensemble
        if "voting" in self.config.model_selection.ensemble_methods:
            try:
                voting_ensemble = VotingRegressor(estimators=base_models)
                
                start_time = time.time()
                voting_ensemble.fit(X_train, y_train_fit)
                training_time = time.time() - start_time
                
                start_pred_time = time.time()
                y_pred = voting_ensemble.predict(X_val)
                prediction_time = time.time() - start_pred_time
                
                metrics = self._calculate_metrics(y_val_fit, y_pred, training_time, prediction_time)
                
                ensemble_model = TrainedModel(
                    model=voting_ensemble,
                    model_name="voting_ensemble",
                    model_type="ensemble_voting",
                    hyperparameters={"base_models": list(trained_models.keys())},
                    metrics=metrics,
                    feature_importance=None,
                    training_metadata={"ensemble_type": "voting", "base_models": len(base_models)},
                    trained_at=datetime.now()
                )
                
                ensemble_models["voting_ensemble"] = ensemble_model
                logger.info(f"Voting ensemble created - RMSE: {metrics.rmse:.4f}")
                
            except Exception as e:
                logger.error(f"Failed to create voting ensemble: {str(e)}")
        
        # Stacking ensemble
        if "staking" in self.config.model_selection.ensemble_methods:
            try:
                # Use linear regression as meta-learner
                stacking_ensemble = StackingRegressor(
                    estimators=base_models,
                    final_estimator=LinearRegression(),
                    cv=3
                )
                
                start_time = time.time()
                stacking_ensemble.fit(X_train, y_train_fit)
                training_time = time.time() - start_time
                
                start_pred_time = time.time()
                y_pred = stacking_ensemble.predict(X_val)
                prediction_time = time.time() - start_pred_time
                
                metrics = self._calculate_metrics(y_val_fit, y_pred, training_time, prediction_time)
                
                ensemble_model = TrainedModel(
                    model=stacking_ensemble,
                    model_name="stacking_ensemble",
                    model_type="ensemble_stacking",
                    hyperparameters={"base_models": list(trained_models.keys()), "meta_learner": "linear_regression"},
                    metrics=metrics,
                    feature_importance=None,
                    training_metadata={"ensemble_type": "stacking", "base_models": len(base_models)},
                    trained_at=datetime.now()
                )
                
                ensemble_models["stacking_ensemble"] = ensemble_model
                logger.info(f"Stacking ensemble created - RMSE: {metrics.rmse:.4f}")
                
            except Exception as e:
                logger.error(f"Failed to create stacking ensemble: {str(e)}")
        
        return ensemble_models
    
    def select_best_model(self, trained_models: Dict[str, TrainedModel]) -> Tuple[str, TrainedModel]:
        """
        Select the best model based on configured criteria
        
        Args:
            trained_models: Dictionary of trained models
            
        Returns:
            Tuple of (best_model_name, best_model)
        """
        if not trained_models:
            raise ValueError("No trained models available for selection")
        
        logger.info("Selecting best model based on configured criteria")
        
        selection_config = self.config.model_selection
        
        # Calculate composite scores for each model
        model_scores = {}
        for model_name, trained_model in trained_models.items():
            composite_score = trained_model.metrics.get_composite_score(selection_config.selection_criteria)
            model_scores[model_name] = composite_score
            
            logger.info(f"{model_name}: composite_score={composite_score:.4f}, "
                       f"rmse={trained_model.metrics.rmse:.4f}, "
                       f"r2={trained_model.metrics.r2_score:.4f}")
        
        # Select best model (highest composite score)
        best_model_name = max(model_scores, key=model_scores.get)
        best_model = trained_models[best_model_name]
        
        logger.info(f"Selected best model: {best_model_name} (score: {model_scores[best_model_name]:.4f})")
        
        return best_model_name, best_model
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray, 
                          training_time: float, prediction_time: float) -> ModelMetrics:
        """Calculate comprehensive metrics for model evaluation"""
        
        # Ensure inputs are numpy arrays
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        
        # Remove any infinite or NaN values
        mask = np.isfinite(y_true) & np.isfinite(y_pred)
        y_true_clean = y_true[mask]
        y_pred_clean = y_pred[mask]
        
        if len(y_true_clean) == 0:
            logger.warning("No valid predictions for metric calculation")
            return ModelMetrics(
                rmse=float('inf'), mae=float('inf'), mape=float('inf'),
                r2_score=-float('inf'), max_error=float('inf'),
                mean_squared_log_error=None, training_time=training_time,
                prediction_time=prediction_time
            )
        
        # Calculate metrics
        rmse = np.sqrt(mean_squared_error(y_true_clean, y_pred_clean))
        mae = mean_absolute_error(y_true_clean, y_pred_clean)
        
        # MAPE (avoid division by zero)
        mask_nonzero = y_true_clean != 0
        if np.sum(mask_nonzero) > 0:
            mape = np.mean(np.abs((y_true_clean[mask_nonzero] - y_pred_clean[mask_nonzero]) / y_true_clean[mask_nonzero])) * 100
        else:
            mape = float('inf')
        
        r2 = r2_score(y_true_clean, y_pred_clean)
        max_err = max_error(y_true_clean, y_pred_clean)
        
        # Mean Squared Log Error (only for positive values)
        msle = None
        if np.all(y_true_clean > 0) and np.all(y_pred_clean > 0):
            try:
                msle = mean_squared_log_error(y_true_clean, y_pred_clean)
            except Exception:
                msle = None
        
        return ModelMetrics(
            rmse=rmse,
            mae=mae,
            mape=mape,
            r2_score=r2,
            max_error=max_err,
            mean_squared_log_error=msle,
            training_time=training_time,
            prediction_time=prediction_time
        )
    
    def _get_feature_importance(self, model: BaseEstimator, feature_names: List[str]) -> Optional[Dict[str, float]]:
        """Extract feature importance from model if available"""
        try:
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                return dict(zip(feature_names, importances.tolist()))
            elif hasattr(model, 'coef_'):
                coefficients = np.abs(model.coef_)
                if len(coefficients.shape) == 1:
                    return dict(zip(feature_names, coefficients.tolist()))
                else:
                    # Multi-output case, use first output
                    return dict(zip(feature_names, coefficients[0].tolist()))
        except Exception as e:
            logger.debug(f"Could not extract feature importance: {str(e)}")
        
        return None
    
    def get_training_summary(self) -> Dict[str, Any]:
        """Get summary of all trained models"""
        if not self.trained_models:
            return {"message": "No models have been trained yet"}
        
        summary = {
            "total_models": len(self.trained_models),
            "models": {}
        }
        
        for model_name, trained_model in self.trained_models.items():
            summary["models"][model_name] = {
                "type": trained_model.model_type,
                "metrics": trained_model.metrics.to_dict(),
                "training_time": trained_model.metrics.training_time,
                "trained_at": trained_model.trained_at.isoformat()
            }
        
        return summary


if __name__ == "__main__":
    # Example usage
    config = get_ml_config_manager()
    trainer = ModelTrainer(config)
    
    # This would normally use real data from the data loader
    print("ModelTrainer initialized successfully")
    print(f"Enabled models: {list(config.get_enabled_models().keys())}")
    print(f"Parallel training: {config.performance.parallel_training}")
    print(f"Ensemble models: {config.model_selection.ensemble_models}")