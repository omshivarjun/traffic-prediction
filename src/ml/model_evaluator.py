"""
Model Evaluation and Metrics System

Comprehensive model evaluation with metrics calculation, visualization,
residual analysis, and model comparison capabilities.
"""

import os
import logging
import json
import warnings
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional, Union
import numpy as np
import pandas as pd

# Visualization libraries
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    plt = None
    sns = None

# Statistical libraries
try:
    from scipy import stats
    from scipy.stats import jarque_bera, shapiro, normaltest
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    stats = None

# Scikit-learn metrics and utilities
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score, max_error,
    mean_squared_log_error, explained_variance_score, median_absolute_error
)
from sklearn.model_selection import learning_curve, validation_curve
from sklearn.inspection import permutation_importance

# Import our components
from config_manager import MLTrainingConfigManager, get_ml_config_manager
from model_trainer import TrainedModel, ModelMetrics

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculates comprehensive evaluation metrics"""
    
    def __init__(self, config: MLTrainingConfigManager):
        self.config = config
    
    def calculate_regression_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """
        Calculate comprehensive regression metrics
        
        Args:
            y_true: True values
            y_pred: Predicted values
            
        Returns:
            Dictionary of calculated metrics
        """
        # Ensure inputs are numpy arrays
        y_true = np.asarray(y_true).flatten()
        y_pred = np.asarray(y_pred).flatten()
        
        # Remove any infinite or NaN values
        mask = np.isfinite(y_true) & np.isfinite(y_pred)
        y_true_clean = y_true[mask]
        y_pred_clean = y_pred[mask]
        
        if len(y_true_clean) == 0:
            return {metric: float('inf') for metric in self.config.evaluation.metrics}
        
        metrics = {}
        
        # Basic regression metrics
        if "rmse" in self.config.evaluation.metrics:
            metrics["rmse"] = np.sqrt(mean_squared_error(y_true_clean, y_pred_clean))
        
        if "mae" in self.config.evaluation.metrics:
            metrics["mae"] = mean_absolute_error(y_true_clean, y_pred_clean)
        
        if "mape" in self.config.evaluation.metrics:
            # MAPE (avoid division by zero)
            mask_nonzero = y_true_clean != 0
            if np.sum(mask_nonzero) > 0:
                metrics["mape"] = np.mean(np.abs((y_true_clean[mask_nonzero] - y_pred_clean[mask_nonzero]) / y_true_clean[mask_nonzero])) * 100
            else:
                metrics["mape"] = float('inf')
        
        if "r2_score" in self.config.evaluation.metrics:
            metrics["r2_score"] = r2_score(y_true_clean, y_pred_clean)
        
        if "max_error" in self.config.evaluation.metrics:
            metrics["max_error"] = max_error(y_true_clean, y_pred_clean)
        
        if "mean_squared_log_error" in self.config.evaluation.metrics:
            # MSLE (only for positive values)
            if np.all(y_true_clean > 0) and np.all(y_pred_clean > 0):
                try:
                    metrics["mean_squared_log_error"] = mean_squared_log_error(y_true_clean, y_pred_clean)
                except Exception:
                    metrics["mean_squared_log_error"] = None
            else:
                metrics["mean_squared_log_error"] = None
        
        # Additional metrics
        try:
            metrics["median_absolute_error"] = median_absolute_error(y_true_clean, y_pred_clean)
            metrics["explained_variance_score"] = explained_variance_score(y_true_clean, y_pred_clean)
            
            # Custom metrics
            residuals = y_true_clean - y_pred_clean
            metrics["mean_residual"] = np.mean(residuals)
            metrics["std_residual"] = np.std(residuals)
            metrics["mean_absolute_percentage_error"] = np.mean(np.abs(residuals / y_true_clean)) * 100 if np.all(y_true_clean != 0) else float('inf')
            
            # Relative metrics
            metrics["relative_rmse"] = metrics["rmse"] / np.mean(y_true_clean) if np.mean(y_true_clean) != 0 else float('inf')
            metrics["normalized_rmse"] = metrics["rmse"] / (np.max(y_true_clean) - np.min(y_true_clean)) if (np.max(y_true_clean) - np.min(y_true_clean)) != 0 else float('inf')
            
        except Exception as e:
            logger.debug(f"Could not calculate additional metrics: {str(e)}")
        
        return metrics
    
    def calculate_prediction_intervals(self, y_true: np.ndarray, y_pred: np.ndarray, 
                                     confidence_level: float = 0.95) -> Dict[str, np.ndarray]:
        """
        Calculate prediction intervals
        
        Args:
            y_true: True values
            y_pred: Predicted values
            confidence_level: Confidence level for intervals
            
        Returns:
            Dictionary with prediction intervals
        """
        if not self.config.evaluation.prediction_intervals:
            return {}
        
        residuals = y_true - y_pred
        residual_std = np.std(residuals)
        
        # Calculate z-score for confidence level
        alpha = 1 - confidence_level
        if SCIPY_AVAILABLE:
            z_score = stats.norm.ppf(1 - alpha/2)
        else:
            # Approximation for common confidence levels
            z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
            z_score = z_scores.get(confidence_level, 1.96)
        
        margin_of_error = z_score * residual_std
        
        return {
            "lower_bound": y_pred - margin_of_error,
            "upper_bound": y_pred + margin_of_error,
            "margin_of_error": margin_of_error,
            "confidence_level": confidence_level
        }


class ResidualAnalyzer:
    """Analyzes model residuals for diagnostic purposes"""
    
    def __init__(self, config: MLTrainingConfigManager):
        self.config = config
    
    def analyze_residuals(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
        """
        Comprehensive residual analysis
        
        Args:
            y_true: True values
            y_pred: Predicted values
            
        Returns:
            Dictionary with residual analysis results
        """
        if not self.config.evaluation.residual_analysis:
            return {}
        
        residuals = y_true - y_pred
        
        analysis = {
            "residual_statistics": self._calculate_residual_statistics(residuals),
            "normality_tests": self._test_residual_normality(residuals),
            "autocorrelation": self._test_residual_autocorrelation(residuals),
            "heteroscedasticity": self._test_heteroscedasticity(residuals, y_pred)
        }
        
        return analysis
    
    def _calculate_residual_statistics(self, residuals: np.ndarray) -> Dict[str, float]:
        """Calculate basic residual statistics"""
        return {
            "mean": float(np.mean(residuals)),
            "std": float(np.std(residuals)),
            "min": float(np.min(residuals)),
            "max": float(np.max(residuals)),
            "median": float(np.median(residuals)),
            "q25": float(np.percentile(residuals, 25)),
            "q75": float(np.percentile(residuals, 75)),
            "skewness": float(stats.skew(residuals)) if SCIPY_AVAILABLE else None,
            "kurtosis": float(stats.kurtosis(residuals)) if SCIPY_AVAILABLE else None
        }
    
    def _test_residual_normality(self, residuals: np.ndarray) -> Dict[str, Any]:
        """Test residual normality"""
        if not SCIPY_AVAILABLE:
            return {"error": "SciPy not available for normality tests"}
        
        results = {}
        
        try:
            # Shapiro-Wilk test (for smaller samples)
            if len(residuals) <= 5000:
                stat, p_value = shapiro(residuals)
                results["shapiro_wilk"] = {"statistic": float(stat), "p_value": float(p_value)}
            
            # Jarque-Bera test
            stat, p_value = jarque_bera(residuals)
            results["jarque_bera"] = {"statistic": float(stat), "p_value": float(p_value)}
            
            # D'Agostino's normality test
            stat, p_value = normaltest(residuals)
            results["dagostino"] = {"statistic": float(stat), "p_value": float(p_value)}
            
        except Exception as e:
            results["error"] = f"Normality tests failed: {str(e)}"
        
        return results
    
    def _test_residual_autocorrelation(self, residuals: np.ndarray) -> Dict[str, Any]:
        """Test residual autocorrelation (Durbin-Watson approximation)"""
        if len(residuals) < 2:
            return {"error": "Insufficient data for autocorrelation test"}
        
        # Simple autocorrelation at lag 1
        autocorr_lag1 = np.corrcoef(residuals[:-1], residuals[1:])[0, 1]
        
        # Durbin-Watson approximation
        diff_residuals = np.diff(residuals)
        dw_statistic = np.sum(diff_residuals**2) / np.sum(residuals**2)
        
        return {
            "autocorrelation_lag1": float(autocorr_lag1),
            "durbin_watson_approx": float(dw_statistic)
        }
    
    def _test_heteroscedasticity(self, residuals: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
        """Test for heteroscedasticity (non-constant variance)"""
        if len(residuals) != len(y_pred):
            return {"error": "Residuals and predictions length mismatch"}
        
        # Simple correlation between absolute residuals and predictions
        abs_residuals = np.abs(residuals)
        correlation = np.corrcoef(abs_residuals, y_pred)[0, 1]
        
        return {
            "residual_prediction_correlation": float(correlation),
            "potential_heteroscedasticity": abs(correlation) > 0.3
        }


class ModelComparator:
    """Compares multiple trained models"""
    
    def __init__(self, config: MLTrainingConfigManager):
        self.config = config
    
    def compare_models(self, trained_models: Dict[str, TrainedModel], 
                      X_test: pd.DataFrame, y_test: pd.DataFrame) -> Dict[str, Any]:
        """
        Compare multiple trained models
        
        Args:
            trained_models: Dictionary of trained models
            X_test: Test features
            y_test: Test targets
            
        Returns:
            Model comparison results
        """
        logger.info(f"Comparing {len(trained_models)} models")
        
        comparison_results = {
            "model_rankings": {},
            "detailed_metrics": {},
            "pairwise_comparisons": {},
            "summary": {}
        }
        
        # Calculate metrics for each model
        model_metrics = {}
        for model_name, trained_model in trained_models.items():
            try:
                # Make predictions
                y_pred = trained_model.model.predict(X_test)
                
                # Handle multi-target case
                if len(y_test.columns) == 1:
                    y_test_eval = y_test.squeeze()
                else:
                    y_test_eval = y_test.iloc[:, 0]
                
                if len(y_pred.shape) > 1 and y_pred.shape[1] > 1:
                    y_pred_eval = y_pred[:, 0]
                else:
                    y_pred_eval = y_pred
                
                # Calculate metrics
                metrics_calc = MetricsCalculator(self.config)
                metrics = metrics_calc.calculate_regression_metrics(y_test_eval, y_pred_eval)
                
                model_metrics[model_name] = metrics
                comparison_results["detailed_metrics"][model_name] = metrics
                
            except Exception as e:
                logger.error(f"Failed to evaluate model {model_name}: {str(e)}")
                model_metrics[model_name] = {"error": str(e)}
        
        # Rank models by primary metric
        primary_metric = self.config.model_selection.primary_metric
        minimize_metric = self.config.model_selection.minimize_metric
        
        valid_models = {name: metrics for name, metrics in model_metrics.items() 
                       if "error" not in metrics and primary_metric in metrics}
        
        if valid_models:
            sorted_models = sorted(valid_models.items(), 
                                 key=lambda x: x[1][primary_metric], 
                                 reverse=not minimize_metric)
            
            comparison_results["model_rankings"] = {
                f"rank_{i+1}": {"model": model_name, "score": metrics[primary_metric]}
                for i, (model_name, metrics) in enumerate(sorted_models)
            }
            
            # Best model
            best_model_name, best_metrics = sorted_models[0]
            comparison_results["best_model"] = {
                "name": best_model_name,
                "metrics": best_metrics
            }
        
        # Summary statistics
        if valid_models:
            metric_names = next(iter(valid_models.values())).keys()
            summary = {}
            
            for metric in metric_names:
                metric_values = [metrics[metric] for metrics in valid_models.values() 
                               if metrics[metric] is not None]
                if metric_values:
                    summary[metric] = {
                        "mean": float(np.mean(metric_values)),
                        "std": float(np.std(metric_values)),
                        "min": float(np.min(metric_values)),
                        "max": float(np.max(metric_values))
                    }
            
            comparison_results["summary"] = summary
        
        return comparison_results
    
    def generate_comparison_report(self, comparison_results: Dict[str, Any]) -> str:
        """Generate a text report of model comparison"""
        
        report_lines = [
            "=" * 80,
            "MODEL COMPARISON REPORT",
            "=" * 80,
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # Best model
        if "best_model" in comparison_results:
            best_model = comparison_results["best_model"]
            report_lines.extend([
                "BEST MODEL:",
                f"  Name: {best_model['name']}",
                f"  Primary Metric ({self.config.model_selection.primary_metric}): {best_model['metrics'][self.config.model_selection.primary_metric]:.4f}",
                ""
            ])
        
        # Model rankings
        if "model_rankings" in comparison_results:
            report_lines.append("MODEL RANKINGS:")
            for rank, info in comparison_results["model_rankings"].items():
                report_lines.append(f"  {rank}: {info['model']} (score: {info['score']:.4f})")
            report_lines.append("")
        
        # Detailed metrics
        if "detailed_metrics" in comparison_results:
            report_lines.append("DETAILED METRICS:")
            for model_name, metrics in comparison_results["detailed_metrics"].items():
                report_lines.append(f"  {model_name}:")
                for metric_name, value in metrics.items():
                    if value is not None and isinstance(value, (int, float)):
                        report_lines.append(f"    {metric_name}: {value:.4f}")
                report_lines.append("")
        
        # Summary statistics
        if "summary" in comparison_results:
            report_lines.append("SUMMARY STATISTICS:")
            for metric_name, stats in comparison_results["summary"].items():
                report_lines.append(f"  {metric_name}:")
                report_lines.append(f"    Mean: {stats['mean']:.4f}")
                report_lines.append(f"    Std:  {stats['std']:.4f}")
                report_lines.append(f"    Min:  {stats['min']:.4f}")
                report_lines.append(f"    Max:  {stats['max']:.4f}")
                report_lines.append("")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)


class VisualizationGenerator:
    """Generates evaluation visualizations"""
    
    def __init__(self, config: MLTrainingConfigManager):
        self.config = config
        self.plot_style_initialized = False
    
    def _initialize_plot_style(self):
        """Initialize plotting style"""
        if not PLOTTING_AVAILABLE or self.plot_style_initialized:
            return
        
        plt.style.use('default')
        sns.set_palette("husl")
        plt.rcParams['figure.figsize'] = (12, 8)
        plt.rcParams['font.size'] = 10
        self.plot_style_initialized = True
    
    def generate_evaluation_plots(self, trained_models: Dict[str, TrainedModel],
                                X_test: pd.DataFrame, y_test: pd.DataFrame,
                                output_dir: str) -> Dict[str, str]:
        """
        Generate comprehensive evaluation plots
        
        Args:
            trained_models: Dictionary of trained models
            X_test: Test features
            y_test: Test targets
            output_dir: Directory to save plots
            
        Returns:
            Dictionary mapping plot types to file paths
        """
        if not PLOTTING_AVAILABLE:
            logger.warning("Matplotlib/Seaborn not available, skipping plot generation")
            return {}
        
        if not self.config.evaluation.generate_plots:
            logger.info("Plot generation disabled in configuration")
            return {}
        
        self._initialize_plot_style()
        os.makedirs(output_dir, exist_ok=True)
        
        generated_plots = {}
        
        # Generate plots for each model
        for model_name, trained_model in trained_models.items():
            try:
                # Make predictions
                y_pred = trained_model.model.predict(X_test)
                
                # Handle multi-target case
                if len(y_test.columns) == 1:
                    y_test_eval = y_test.squeeze()
                else:
                    y_test_eval = y_test.iloc[:, 0]
                
                if len(y_pred.shape) > 1 and y_pred.shape[1] > 1:
                    y_pred_eval = y_pred[:, 0]
                else:
                    y_pred_eval = y_pred
                
                # Generate individual plots
                model_plots = self._generate_model_plots(
                    model_name, y_test_eval, y_pred_eval, 
                    trained_model, X_test, output_dir
                )
                
                generated_plots.update(model_plots)
                
            except Exception as e:
                logger.error(f"Failed to generate plots for {model_name}: {str(e)}")
        
        # Generate comparison plots
        try:
            comparison_plots = self._generate_comparison_plots(
                trained_models, X_test, y_test, output_dir
            )
            generated_plots.update(comparison_plots)
        except Exception as e:
            logger.error(f"Failed to generate comparison plots: {str(e)}")
        
        return generated_plots
    
    def _generate_model_plots(self, model_name: str, y_true: np.ndarray, y_pred: np.ndarray,
                            trained_model: TrainedModel, X_test: pd.DataFrame, 
                            output_dir: str) -> Dict[str, str]:
        """Generate plots for a single model"""
        plots = {}
        
        # Residual plot
        if "residual_plot" in self.config.evaluation.plot_types:
            plot_path = self._create_residual_plot(model_name, y_true, y_pred, output_dir)
            if plot_path:
                plots[f"{model_name}_residual_plot"] = plot_path
        
        # Prediction vs Actual plot
        if "prediction_vs_actual" in self.config.evaluation.plot_types:
            plot_path = self._create_prediction_vs_actual_plot(model_name, y_true, y_pred, output_dir)
            if plot_path:
                plots[f"{model_name}_prediction_vs_actual"] = plot_path
        
        # Feature importance plot
        if ("feature_importance" in self.config.evaluation.plot_types and 
            trained_model.feature_importance is not None):
            plot_path = self._create_feature_importance_plot(model_name, trained_model.feature_importance, output_dir)
            if plot_path:
                plots[f"{model_name}_feature_importance"] = plot_path
        
        return plots
    
    def _create_residual_plot(self, model_name: str, y_true: np.ndarray, y_pred: np.ndarray, 
                            output_dir: str) -> Optional[str]:
        """Create residual plot"""
        try:
            residuals = y_true - y_pred
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Residuals vs Predicted
            ax1.scatter(y_pred, residuals, alpha=0.6)
            ax1.axhline(y=0, color='red', linestyle='--')
            ax1.set_xlabel('Predicted Values')
            ax1.set_ylabel('Residuals')
            ax1.set_title(f'{model_name} - Residuals vs Predicted')
            ax1.grid(True, alpha=0.3)
            
            # Residual histogram
            ax2.hist(residuals, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
            ax2.set_xlabel('Residuals')
            ax2.set_ylabel('Frequency')
            ax2.set_title(f'{model_name} - Residual Distribution')
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            plot_path = os.path.join(output_dir, f"{model_name}_residual_plot.png")
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return plot_path
            
        except Exception as e:
            logger.error(f"Failed to create residual plot for {model_name}: {str(e)}")
            return None
    
    def _create_prediction_vs_actual_plot(self, model_name: str, y_true: np.ndarray, y_pred: np.ndarray,
                                        output_dir: str) -> Optional[str]:
        """Create prediction vs actual plot"""
        try:
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Scatter plot
            ax.scatter(y_true, y_pred, alpha=0.6)
            
            # Perfect prediction line
            min_val = min(np.min(y_true), np.min(y_pred))
            max_val = max(np.max(y_true), np.max(y_pred))
            ax.plot([min_val, max_val], [min_val, max_val], 'r--', label='Perfect Prediction')
            
            # Calculate R²
            r2 = np.corrcoef(y_true, y_pred)[0, 1] ** 2
            
            ax.set_xlabel('Actual Values')
            ax.set_ylabel('Predicted Values')
            ax.set_title(f'{model_name} - Prediction vs Actual (R² = {r2:.3f})')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Add equality line
            ax.set_aspect('equal', adjustable='box')
            
            plot_path = os.path.join(output_dir, f"{model_name}_prediction_vs_actual.png")
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return plot_path
            
        except Exception as e:
            logger.error(f"Failed to create prediction vs actual plot for {model_name}: {str(e)}")
            return None
    
    def _create_feature_importance_plot(self, model_name: str, feature_importance: Dict[str, float],
                                      output_dir: str) -> Optional[str]:
        """Create feature importance plot"""
        try:
            # Sort by importance
            sorted_features = sorted(feature_importance.items(), key=lambda x: abs(x[1]), reverse=True)
            
            # Take top 20 features
            top_features = sorted_features[:20]
            
            if not top_features:
                return None
            
            features, importances = zip(*top_features)
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            y_pos = np.arange(len(features))
            bars = ax.barh(y_pos, importances)
            
            # Color bars based on importance
            colors = plt.cm.viridis(np.linspace(0, 1, len(bars)))
            for bar, color in zip(bars, colors):
                bar.set_color(color)
            
            ax.set_yticks(y_pos)
            ax.set_yticklabels(features)
            ax.invert_yaxis()
            ax.set_xlabel('Importance')
            ax.set_title(f'{model_name} - Feature Importance')
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            plot_path = os.path.join(output_dir, f"{model_name}_feature_importance.png")
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return plot_path
            
        except Exception as e:
            logger.error(f"Failed to create feature importance plot for {model_name}: {str(e)}")
            return None
    
    def _generate_comparison_plots(self, trained_models: Dict[str, TrainedModel],
                                 X_test: pd.DataFrame, y_test: pd.DataFrame,
                                 output_dir: str) -> Dict[str, str]:
        """Generate model comparison plots"""
        plots = {}
        
        try:
            # Metrics comparison bar plot
            plot_path = self._create_metrics_comparison_plot(trained_models, X_test, y_test, output_dir)
            if plot_path:
                plots["metrics_comparison"] = plot_path
        except Exception as e:
            logger.error(f"Failed to create metrics comparison plot: {str(e)}")
        
        return plots
    
    def _create_metrics_comparison_plot(self, trained_models: Dict[str, TrainedModel],
                                      X_test: pd.DataFrame, y_test: pd.DataFrame,
                                      output_dir: str) -> Optional[str]:
        """Create metrics comparison plot"""
        try:
            metrics_data = {}
            
            for model_name, trained_model in trained_models.items():
                # Get metrics from the trained model
                model_metrics = trained_model.metrics.to_dict()
                
                # Filter to numeric metrics for plotting
                numeric_metrics = {k: v for k, v in model_metrics.items() 
                                 if isinstance(v, (int, float)) and v is not None and not np.isinf(v)}
                
                metrics_data[model_name] = numeric_metrics
            
            if not metrics_data:
                return None
            
            # Create DataFrame for plotting
            df_metrics = pd.DataFrame(metrics_data).T
            
            # Select key metrics for plotting
            key_metrics = ['rmse', 'mae', 'r2_score', 'mape']
            available_metrics = [m for m in key_metrics if m in df_metrics.columns]
            
            if not available_metrics:
                return None
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            axes = axes.flatten()
            
            for i, metric in enumerate(available_metrics[:4]):
                ax = axes[i]
                
                # Bar plot
                model_names = df_metrics.index
                values = df_metrics[metric]
                
                bars = ax.bar(model_names, values)
                
                # Color bars
                colors = plt.cm.Set3(np.linspace(0, 1, len(bars)))
                for bar, color in zip(bars, colors):
                    bar.set_color(color)
                
                ax.set_title(f'{metric.upper()} Comparison')
                ax.set_ylabel(metric.upper())
                ax.tick_params(axis='x', rotation=45)
                ax.grid(True, alpha=0.3)
                
                # Add value labels on bars
                for bar, value in zip(bars, values):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{value:.3f}', ha='center', va='bottom')
            
            # Hide unused subplots
            for i in range(len(available_metrics), 4):
                axes[i].set_visible(False)
            
            plt.tight_layout()
            
            plot_path = os.path.join(output_dir, "model_metrics_comparison.png")
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return plot_path
            
        except Exception as e:
            logger.error(f"Failed to create metrics comparison plot: {str(e)}")
            return None


class ModelEvaluator:
    """Main model evaluation orchestrator"""
    
    def __init__(self, config: MLTrainingConfigManager):
        """
        Initialize model evaluator
        
        Args:
            config: ML training configuration
        """
        self.config = config
        self.metrics_calculator = MetricsCalculator(config)
        self.residual_analyzer = ResidualAnalyzer(config)
        self.model_comparator = ModelComparator(config)
        self.visualization_generator = VisualizationGenerator(config)
        
        logger.info("ModelEvaluator initialized")
    
    def evaluate_single_model(self, trained_model: TrainedModel,
                             X_test: pd.DataFrame, y_test: pd.DataFrame) -> Dict[str, Any]:
        """
        Comprehensive evaluation of a single model
        
        Args:
            trained_model: Trained model to evaluate
            X_test: Test features
            y_test: Test targets
            
        Returns:
            Comprehensive evaluation results
        """
        logger.info(f"Evaluating model: {trained_model.model_name}")
        
        try:
            # Make predictions
            y_pred = trained_model.model.predict(X_test)
            
            # Handle multi-target case
            if len(y_test.columns) == 1:
                y_test_eval = y_test.squeeze()
            else:
                y_test_eval = y_test.iloc[:, 0]
            
            if len(y_pred.shape) > 1 and y_pred.shape[1] > 1:
                y_pred_eval = y_pred[:, 0]
            else:
                y_pred_eval = y_pred
            
            # Calculate metrics
            metrics = self.metrics_calculator.calculate_regression_metrics(y_test_eval, y_pred_eval)
            
            # Prediction intervals
            prediction_intervals = self.metrics_calculator.calculate_prediction_intervals(
                y_test_eval, y_pred_eval, self.config.evaluation.confidence_level
            )
            
            # Residual analysis
            residual_analysis = self.residual_analyzer.analyze_residuals(y_test_eval, y_pred_eval)
            
            evaluation_results = {
                "model_info": trained_model.to_dict(),
                "test_metrics": metrics,
                "prediction_intervals": prediction_intervals,
                "residual_analysis": residual_analysis,
                "evaluation_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Model {trained_model.model_name} evaluation completed")
            
            return evaluation_results
            
        except Exception as e:
            logger.error(f"Failed to evaluate model {trained_model.model_name}: {str(e)}")
            return {"error": str(e)}
    
    def evaluate_all_models(self, trained_models: Dict[str, TrainedModel],
                           X_test: pd.DataFrame, y_test: pd.DataFrame,
                           output_dir: str = "evaluation_results") -> Dict[str, Any]:
        """
        Comprehensive evaluation of all models with comparison
        
        Args:
            trained_models: Dictionary of trained models
            X_test: Test features
            y_test: Test targets
            output_dir: Directory to save results
            
        Returns:
            Complete evaluation results
        """
        logger.info(f"Evaluating {len(trained_models)} models")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Individual model evaluations
        individual_evaluations = {}
        for model_name, trained_model in trained_models.items():
            evaluation = self.evaluate_single_model(trained_model, X_test, y_test)
            individual_evaluations[model_name] = evaluation
        
        # Model comparison
        comparison_results = self.model_comparator.compare_models(trained_models, X_test, y_test)
        
        # Generate visualizations
        generated_plots = self.visualization_generator.generate_evaluation_plots(
            trained_models, X_test, y_test, output_dir
        )
        
        # Generate comparison report
        comparison_report = self.model_comparator.generate_comparison_report(comparison_results)
        
        # Save comparison report
        report_path = os.path.join(output_dir, "model_comparison_report.txt")
        with open(report_path, 'w') as f:
            f.write(comparison_report)
        
        # Complete results
        complete_results = {
            "individual_evaluations": individual_evaluations,
            "model_comparison": comparison_results,
            "generated_plots": generated_plots,
            "comparison_report_path": report_path,
            "evaluation_metadata": {
                "total_models": len(trained_models),
                "test_samples": len(X_test),
                "test_features": len(X_test.columns),
                "evaluation_timestamp": datetime.now().isoformat(),
                "output_directory": output_dir
            }
        }
        
        # Save complete results
        results_path = os.path.join(output_dir, "complete_evaluation_results.json")
        with open(results_path, 'w') as f:
            # Convert numpy types for JSON serialization
            json_results = self._convert_for_json(complete_results)
            json.dump(json_results, f, indent=2)
        
        logger.info(f"Complete model evaluation saved to: {output_dir}")
        
        return complete_results
    
    def _convert_for_json(self, obj: Any) -> Any:
        """Convert numpy types and other non-serializable objects for JSON"""
        if isinstance(obj, dict):
            return {key: self._convert_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_for_json(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif pd.isna(obj):
            return None
        else:
            return obj


if __name__ == "__main__":
    # Example usage
    config = get_ml_config_manager()
    evaluator = ModelEvaluator(config)
    
    print("ModelEvaluator initialized successfully")
    print(f"Configured metrics: {config.evaluation.metrics}")
    print(f"Generate plots: {config.evaluation.generate_plots}")
    print(f"Plot types: {config.evaluation.plot_types}")
    print(f"Residual analysis: {config.evaluation.residual_analysis}")
    print(f"Prediction intervals: {config.evaluation.prediction_intervals}")