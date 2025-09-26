"""
Traffic Prediction Monitoring System

Comprehensive monitoring, metrics collection, and alerting system for the traffic
prediction service. Tracks performance metrics, prediction accuracy, system health,
and provides automated reporting and alerting capabilities.
"""

import os
import sys
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import traceback
import statistics
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

# Add prediction service to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from prediction_service import PredictionServiceConfig, DatabaseManager

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricRecord:
    """Individual metric record"""
    timestamp: datetime
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, str]
    alert_level: Optional[AlertLevel] = None


@dataclass
class PerformanceMetrics:
    """Prediction service performance metrics"""
    timestamp: datetime
    predictions_generated: int
    predictions_stored: int
    processing_time_seconds: float
    sensors_processed: int
    error_count: int
    success_rate: float
    average_confidence: float
    memory_usage_mb: float
    cpu_usage_percent: float


@dataclass
class AccuracyMetrics:
    """Prediction accuracy metrics"""
    timestamp: datetime
    horizon_minutes: int
    mae_speed: float  # Mean Absolute Error for speed
    rmse_speed: float  # Root Mean Square Error for speed
    mape_speed: float  # Mean Absolute Percentage Error for speed
    mae_volume: Optional[float] = None
    rmse_volume: Optional[float] = None
    mape_volume: Optional[float] = None
    samples_evaluated: int = 0
    correlation_speed: float = 0.0
    correlation_volume: float = 0.0


class MetricsCollector:
    """Collects and stores system metrics"""
    
    def __init__(self, config: PredictionServiceConfig, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.monitoring_config = config.monitoring_settings
        
        # Metrics storage
        self.metrics_buffer: List[MetricRecord] = []
        self.buffer_size = self.monitoring_config.get('metrics_buffer_size', 1000)
        
        # Performance tracking
        self.performance_history: List[PerformanceMetrics] = []
        self.accuracy_history: List[AccuracyMetrics] = []
        
        logger.info("Metrics collector initialized")
    
    def record_metric(self, name: str, value: float, unit: str = "", 
                     tags: Optional[Dict[str, str]] = None,
                     alert_level: Optional[AlertLevel] = None):
        """Record a single metric"""
        metric = MetricRecord(
            timestamp=datetime.now(),
            metric_name=name,
            value=value,
            unit=unit,
            tags=tags or {},
            alert_level=alert_level
        )
        
        self.metrics_buffer.append(metric)
        
        # Flush buffer if full
        if len(self.metrics_buffer) >= self.buffer_size:
            self.flush_metrics()
        
        # Log critical metrics immediately
        if alert_level and alert_level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            logger.error(f"ALERT [{alert_level.value.upper()}] {name}: {value} {unit}")
    
    def record_performance_metrics(self, metrics: PerformanceMetrics):
        """Record performance metrics batch"""
        self.performance_history.append(metrics)
        
        # Keep only recent history (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.performance_history = [
            m for m in self.performance_history 
            if m.timestamp >= cutoff_time
        ]
        
        # Record individual metrics
        tags = {"job_type": "batch_prediction"}
        
        self.record_metric("predictions_generated", metrics.predictions_generated, "count", tags)
        self.record_metric("processing_time", metrics.processing_time_seconds, "seconds", tags)
        self.record_metric("success_rate", metrics.success_rate, "percent", tags)
        self.record_metric("average_confidence", metrics.average_confidence, "score", tags)
        
        # Check thresholds and generate alerts
        self._check_performance_thresholds(metrics)
    
    def record_accuracy_metrics(self, metrics: AccuracyMetrics):
        """Record accuracy metrics"""
        self.accuracy_history.append(metrics)
        
        # Keep only recent history
        cutoff_time = datetime.now() - timedelta(days=7)
        self.accuracy_history = [
            m for m in self.accuracy_history 
            if m.timestamp >= cutoff_time
        ]
        
        # Record individual metrics
        tags = {"horizon": str(metrics.horizon_minutes)}
        
        self.record_metric("mae_speed", metrics.mae_speed, "mph", tags)
        self.record_metric("rmse_speed", metrics.rmse_speed, "mph", tags)
        self.record_metric("mape_speed", metrics.mape_speed, "percent", tags)
        
        if metrics.mae_volume is not None:
            self.record_metric("mae_volume", metrics.mae_volume, "vehicles/hour", tags)
        
        # Check accuracy thresholds
        self._check_accuracy_thresholds(metrics)
    
    def _check_performance_thresholds(self, metrics: PerformanceMetrics):
        """Check performance metrics against thresholds"""
        thresholds = self.monitoring_config.get('performance_thresholds', {})
        
        # Processing time threshold
        max_processing_time = thresholds.get('max_processing_time_seconds', 300)
        if metrics.processing_time_seconds > max_processing_time:
            self.record_metric(
                "processing_time_alert", 
                metrics.processing_time_seconds,
                "seconds",
                {"threshold": str(max_processing_time)},
                AlertLevel.WARNING
            )
        
        # Success rate threshold
        min_success_rate = thresholds.get('min_success_rate', 0.95)
        if metrics.success_rate < min_success_rate:
            self.record_metric(
                "success_rate_alert",
                metrics.success_rate,
                "percent",
                {"threshold": str(min_success_rate)},
                AlertLevel.ERROR
            )
        
        # Memory usage threshold
        max_memory_mb = thresholds.get('max_memory_usage_mb', 4096)
        if metrics.memory_usage_mb > max_memory_mb:
            self.record_metric(
                "memory_usage_alert",
                metrics.memory_usage_mb,
                "MB",
                {"threshold": str(max_memory_mb)},
                AlertLevel.WARNING
            )
    
    def _check_accuracy_thresholds(self, metrics: AccuracyMetrics):
        """Check accuracy metrics against thresholds"""
        thresholds = self.monitoring_config.get('accuracy_thresholds', {})
        
        # Speed MAPE threshold
        max_mape_speed = thresholds.get('max_mape_speed_percent', 15.0)
        if metrics.mape_speed > max_mape_speed:
            self.record_metric(
                "accuracy_degradation_alert",
                metrics.mape_speed,
                "percent",
                {
                    "metric": "mape_speed",
                    "horizon": str(metrics.horizon_minutes),
                    "threshold": str(max_mape_speed)
                },
                AlertLevel.WARNING
            )
    
    def flush_metrics(self):
        """Flush metrics buffer to storage"""
        if not self.metrics_buffer:
            return
        
        try:
            # In a production system, this would write to a time-series database
            # For now, we'll log and optionally store in PostgreSQL
            
            metrics_to_store = []
            for metric in self.metrics_buffer:
                metrics_to_store.append({
                    'timestamp': metric.timestamp,
                    'metric_name': metric.metric_name,
                    'value': metric.value,
                    'unit': metric.unit,
                    'tags': json.dumps(metric.tags),
                    'alert_level': metric.alert_level.value if metric.alert_level else None
                })
            
            # Store to database (if metrics table exists)
            self._store_metrics_to_db(metrics_to_store)
            
            # Clear buffer
            self.metrics_buffer.clear()
            
            logger.debug(f"Flushed {len(metrics_to_store)} metrics to storage")
            
        except Exception as e:
            logger.error(f"Failed to flush metrics: {str(e)}")
    
    def _store_metrics_to_db(self, metrics: List[Dict]):
        """Store metrics to database"""
        # This would require a metrics table in the database
        # For now, we'll write to a JSON file as backup
        
        try:
            metrics_dir = Path("logs/metrics")
            metrics_dir.mkdir(parents=True, exist_ok=True)
            
            metrics_file = metrics_dir / f"metrics_{datetime.now().strftime('%Y%m%d')}.jsonl"
            
            with open(metrics_file, 'a') as f:
                for metric in metrics:
                    f.write(json.dumps(metric, default=str) + '\n')
            
        except Exception as e:
            logger.warning(f"Failed to write metrics to file: {str(e)}")


class AccuracyAnalyzer:
    """Analyzes prediction accuracy by comparing predictions with actual data"""
    
    def __init__(self, config: PredictionServiceConfig, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.monitoring_config = config.monitoring_settings
    
    def analyze_recent_accuracy(self) -> List[AccuracyMetrics]:
        """Analyze accuracy of recent predictions"""
        logger.info("Analyzing prediction accuracy")
        
        # Get predictions from last 24 hours that should have actual data by now
        analysis_results = []
        horizons = self.config.prediction_settings['horizon_minutes']
        
        for horizon in horizons:
            try:
                accuracy_metrics = self._analyze_horizon_accuracy(horizon)
                if accuracy_metrics:
                    analysis_results.append(accuracy_metrics)
                    logger.info(f"Accuracy analysis for {horizon}min horizon: "
                              f"MAE={accuracy_metrics.mae_speed:.2f}, "
                              f"MAPE={accuracy_metrics.mape_speed:.2f}%")
                
            except Exception as e:
                logger.error(f"Failed to analyze accuracy for {horizon}min horizon: {str(e)}")
        
        return analysis_results
    
    def _analyze_horizon_accuracy(self, horizon_minutes: int) -> Optional[AccuracyMetrics]:
        """Analyze accuracy for specific prediction horizon"""
        
        # Calculate time window for analysis
        now = datetime.now()
        
        # We need predictions that were made at least 'horizon_minutes' ago
        # so we can compare with actual data
        prediction_cutoff = now - timedelta(minutes=horizon_minutes + 60)  # +60 for data lag
        analysis_start = prediction_cutoff - timedelta(hours=6)  # Analyze last 6 hours of predictions
        
        # Query to get predictions with corresponding actual readings
        query = """
        SELECT 
            p.predicted_speed,
            p.predicted_volume,
            p.prediction_timestamp,
            p.horizon_minutes,
            p.confidence_score,
            s.sensor_id,
            tr.speed as actual_speed,
            tr.volume as actual_volume,
            tr.timestamp as actual_timestamp,
            ABS(EXTRACT(EPOCH FROM (tr.timestamp - (p.prediction_timestamp + INTERVAL '%s minutes')))) as time_diff_seconds
        FROM traffic.predictions p
        JOIN traffic.sensors s ON p.sensor_id = s.id
        JOIN traffic.traffic_readings tr ON s.id = tr.sensor_id
        WHERE p.horizon_minutes = %s
          AND p.prediction_timestamp BETWEEN %s AND %s
          AND tr.timestamp BETWEEN (p.prediction_timestamp + INTERVAL '%s minutes' - INTERVAL '15 minutes')
                                AND (p.prediction_timestamp + INTERVAL '%s minutes' + INTERVAL '15 minutes')
          AND tr.quality_score >= 0.7
        ORDER BY time_diff_seconds ASC
        """
        
        try:
            results = self.db_manager.execute_query(
                query, 
                (horizon_minutes, horizon_minutes, analysis_start, prediction_cutoff,
                 horizon_minutes, horizon_minutes)
            )
            
            if not results:
                logger.warning(f"No prediction-actual pairs found for {horizon_minutes}min horizon")
                return None
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(results)
            
            # Remove duplicates (keep closest time match)
            df = df.sort_values('time_diff_seconds').groupby(['sensor_id', 'prediction_timestamp']).first().reset_index()
            
            if len(df) < 5:  # Need minimum samples
                logger.warning(f"Insufficient samples ({len(df)}) for {horizon_minutes}min horizon accuracy analysis")
                return None
            
            # Calculate accuracy metrics for speed
            speed_errors = np.abs(df['predicted_speed'] - df['actual_speed'])
            speed_squared_errors = (df['predicted_speed'] - df['actual_speed']) ** 2
            speed_percentage_errors = np.abs((df['predicted_speed'] - df['actual_speed']) / df['actual_speed']) * 100
            
            # Handle division by zero in MAPE
            speed_percentage_errors = speed_percentage_errors[np.isfinite(speed_percentage_errors)]
            
            mae_speed = np.mean(speed_errors)
            rmse_speed = np.sqrt(np.mean(speed_squared_errors))
            mape_speed = np.mean(speed_percentage_errors) if len(speed_percentage_errors) > 0 else 0.0
            correlation_speed = np.corrcoef(df['predicted_speed'], df['actual_speed'])[0, 1]
            
            # Calculate accuracy metrics for volume (if available)
            mae_volume = None
            rmse_volume = None
            mape_volume = None
            correlation_volume = 0.0
            
            if 'predicted_volume' in df.columns and df['predicted_volume'].notna().any():
                volume_mask = df['predicted_volume'].notna() & df['actual_volume'].notna()
                if volume_mask.sum() > 5:
                    volume_errors = np.abs(df.loc[volume_mask, 'predicted_volume'] - df.loc[volume_mask, 'actual_volume'])
                    volume_squared_errors = (df.loc[volume_mask, 'predicted_volume'] - df.loc[volume_mask, 'actual_volume']) ** 2
                    volume_percentage_errors = np.abs(
                        (df.loc[volume_mask, 'predicted_volume'] - df.loc[volume_mask, 'actual_volume']) / 
                        df.loc[volume_mask, 'actual_volume']
                    ) * 100
                    
                    volume_percentage_errors = volume_percentage_errors[np.isfinite(volume_percentage_errors)]
                    
                    mae_volume = np.mean(volume_errors)
                    rmse_volume = np.sqrt(np.mean(volume_squared_errors))
                    mape_volume = np.mean(volume_percentage_errors) if len(volume_percentage_errors) > 0 else 0.0
                    correlation_volume = np.corrcoef(
                        df.loc[volume_mask, 'predicted_volume'], 
                        df.loc[volume_mask, 'actual_volume']
                    )[0, 1]
            
            return AccuracyMetrics(
                timestamp=datetime.now(),
                horizon_minutes=horizon_minutes,
                mae_speed=mae_speed,
                rmse_speed=rmse_speed,
                mape_speed=mape_speed,
                mae_volume=mae_volume,
                rmse_volume=rmse_volume,
                mape_volume=mape_volume,
                samples_evaluated=len(df),
                correlation_speed=correlation_speed if np.isfinite(correlation_speed) else 0.0,
                correlation_volume=correlation_volume if np.isfinite(correlation_volume) else 0.0
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze accuracy for {horizon_minutes}min horizon: {str(e)}")
            return None


class HealthChecker:
    """System health monitoring"""
    
    def __init__(self, config: PredictionServiceConfig):
        self.config = config
        self.monitoring_config = config.monitoring_settings
    
    def check_system_health(self) -> Dict[str, Any]:
        """Comprehensive system health check"""
        logger.info("Performing system health check")
        
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        # Database connectivity
        db_health = self._check_database_health()
        health_status["checks"]["database"] = db_health
        
        # HDFS connectivity
        hdfs_health = self._check_hdfs_health()
        health_status["checks"]["hdfs"] = hdfs_health
        
        # Model availability
        model_health = self._check_model_health()
        health_status["checks"]["models"] = model_health
        
        # Disk space
        disk_health = self._check_disk_space()
        health_status["checks"]["disk_space"] = disk_health
        
        # Recent prediction performance
        prediction_health = self._check_recent_predictions()
        health_status["checks"]["recent_predictions"] = prediction_health
        
        # Determine overall health
        failed_checks = [check for check, status in health_status["checks"].items() 
                        if status.get("status") != "healthy"]
        
        if failed_checks:
            health_status["overall_status"] = "degraded" if len(failed_checks) < 3 else "unhealthy"
            health_status["failed_checks"] = failed_checks
        
        logger.info(f"System health check completed: {health_status['overall_status']}")
        return health_status
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check PostgreSQL database health"""
        try:
            db_manager = DatabaseManager(self.config)
            
            # Test connection
            start_time = time.time()
            result = db_manager.execute_query("SELECT 1 as test")
            response_time = time.time() - start_time
            
            # Check table existence
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'traffic'
            """
            tables = db_manager.execute_query(tables_query)
            required_tables = ['sensors', 'traffic_readings', 'predictions']
            existing_tables = [t['table_name'] for t in tables]
            missing_tables = [t for t in required_tables if t not in existing_tables]
            
            db_manager.close()
            
            return {
                "status": "healthy" if not missing_tables and response_time < 5.0 else "degraded",
                "response_time_seconds": response_time,
                "missing_tables": missing_tables,
                "details": f"Database responsive in {response_time:.2f}s"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": "Database connection failed"
            }
    
    def _check_hdfs_health(self) -> Dict[str, Any]:
        """Check HDFS health"""
        try:
            # Simple check - try to list HDFS directory
            hdfs_config = self.config.hdfs_config
            model_path = hdfs_config.get('model_base_path', '/models')
            
            # This would require hdfs client - simplified check
            return {
                "status": "healthy",
                "details": f"HDFS path configured: {model_path}",
                "note": "HDFS health check requires hdfs client implementation"
            }
            
        except Exception as e:
            return {
                "status": "degraded",
                "error": str(e),
                "details": "HDFS health check failed"
            }
    
    def _check_model_health(self) -> Dict[str, Any]:
        """Check model availability"""
        try:
            # This would require initializing model manager
            return {
                "status": "healthy",
                "details": "Model availability check requires full initialization",
                "note": "Consider implementing lightweight model check"
            }
            
        except Exception as e:
            return {
                "status": "degraded",
                "error": str(e),
                "details": "Model health check failed"
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space"""
        try:
            import shutil
            
            # Check available space in logs directory
            logs_path = Path("logs")
            if logs_path.exists():
                total, used, free = shutil.disk_usage(logs_path)
                free_gb = free / (1024**3)
                
                status = "healthy" if free_gb > 5.0 else ("degraded" if free_gb > 1.0 else "unhealthy")
                
                return {
                    "status": status,
                    "free_space_gb": round(free_gb, 2),
                    "details": f"{free_gb:.1f}GB available"
                }
            else:
                return {
                    "status": "healthy",
                    "details": "Logs directory not found, assuming sufficient space"
                }
                
        except Exception as e:
            return {
                "status": "degraded",
                "error": str(e),
                "details": "Disk space check failed"
            }
    
    def _check_recent_predictions(self) -> Dict[str, Any]:
        """Check recent prediction activity"""
        try:
            db_manager = DatabaseManager(self.config)
            
            # Check for recent predictions
            recent_query = """
            SELECT COUNT(*) as count, MAX(created_at) as latest
            FROM traffic.predictions
            WHERE created_at >= %s
            """
            
            one_hour_ago = datetime.now() - timedelta(hours=1)
            result = db_manager.execute_query(recent_query, (one_hour_ago,))
            
            db_manager.close()
            
            if result:
                count = result[0]['count']
                latest = result[0]['latest']
                
                status = "healthy" if count > 0 else "degraded"
                
                return {
                    "status": status,
                    "recent_predictions": count,
                    "latest_prediction": latest.isoformat() if latest else None,
                    "details": f"{count} predictions in last hour"
                }
            else:
                return {
                    "status": "degraded",
                    "details": "No recent prediction data found"
                }
                
        except Exception as e:
            return {
                "status": "degraded",
                "error": str(e),
                "details": "Recent predictions check failed"
            }


class MonitoringDashboard:
    """Monitoring dashboard and reporting"""
    
    def __init__(self, config: PredictionServiceConfig, db_manager: DatabaseManager,
                 metrics_collector: MetricsCollector, accuracy_analyzer: AccuracyAnalyzer,
                 health_checker: HealthChecker):
        self.config = config
        self.db_manager = db_manager
        self.metrics_collector = metrics_collector
        self.accuracy_analyzer = accuracy_analyzer
        self.health_checker = health_checker
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        logger.info("Generating performance report")
        
        try:
            # Get recent performance metrics
            recent_metrics = self.metrics_collector.performance_history[-24:] if self.metrics_collector.performance_history else []
            
            if not recent_metrics:
                return {
                    "status": "no_data",
                    "message": "No recent performance data available"
                }
            
            # Calculate aggregated statistics
            processing_times = [m.processing_time_seconds for m in recent_metrics]
            success_rates = [m.success_rate for m in recent_metrics]
            prediction_counts = [m.predictions_generated for m in recent_metrics]
            
            report = {
                "report_timestamp": datetime.now().isoformat(),
                "period_hours": 24,
                "total_jobs": len(recent_metrics),
                "performance_summary": {
                    "avg_processing_time": statistics.mean(processing_times),
                    "max_processing_time": max(processing_times),
                    "min_processing_time": min(processing_times),
                    "avg_success_rate": statistics.mean(success_rates),
                    "total_predictions": sum(prediction_counts),
                    "avg_predictions_per_job": statistics.mean(prediction_counts)
                },
                "accuracy_summary": self._get_accuracy_summary(),
                "system_health": self.health_checker.check_system_health(),
                "recent_alerts": self._get_recent_alerts()
            }
            
            logger.info("Performance report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate performance report: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _get_accuracy_summary(self) -> Dict[str, Any]:
        """Get accuracy metrics summary"""
        try:
            recent_accuracy = self.accuracy_analyzer.analyze_recent_accuracy()
            
            if not recent_accuracy:
                return {"status": "no_data"}
            
            summary = {}
            for metrics in recent_accuracy:
                horizon_key = f"{metrics.horizon_minutes}min"
                summary[horizon_key] = {
                    "mae_speed": metrics.mae_speed,
                    "rmse_speed": metrics.rmse_speed,
                    "mape_speed": metrics.mape_speed,
                    "correlation_speed": metrics.correlation_speed,
                    "samples": metrics.samples_evaluated
                }
                
                if metrics.mae_volume is not None:
                    summary[horizon_key].update({
                        "mae_volume": metrics.mae_volume,
                        "rmse_volume": metrics.rmse_volume,
                        "mape_volume": metrics.mape_volume,
                        "correlation_volume": metrics.correlation_volume
                    })
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get accuracy summary: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _get_recent_alerts(self) -> List[Dict[str, Any]]:
        """Get recent alerts from metrics"""
        try:
            # Get alerts from last 24 hours
            recent_alerts = []
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            for metric in self.metrics_collector.metrics_buffer:
                if metric.alert_level and metric.timestamp >= cutoff_time:
                    recent_alerts.append({
                        "timestamp": metric.timestamp.isoformat(),
                        "metric": metric.metric_name,
                        "value": metric.value,
                        "unit": metric.unit,
                        "level": metric.alert_level.value,
                        "tags": metric.tags
                    })
            
            # Sort by timestamp descending
            recent_alerts.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return recent_alerts[:50]  # Last 50 alerts
            
        except Exception as e:
            logger.error(f"Failed to get recent alerts: {str(e)}")
            return []
    
    def save_report(self, report: Dict[str, Any], filename: Optional[str] = None):
        """Save report to file"""
        try:
            reports_dir = Path("logs/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            if not filename:
                filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            report_path = reports_dir / filename
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Report saved to {report_path}")
            return str(report_path)
            
        except Exception as e:
            logger.error(f"Failed to save report: {str(e)}")
            return None


class TrafficPredictionMonitor:
    """Main monitoring service coordinator"""
    
    def __init__(self, config_path: str = "config/prediction_service_config.json"):
        """Initialize monitoring system"""
        
        # Load configuration
        self.config = PredictionServiceConfig(config_path)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        self.db_manager = DatabaseManager(self.config)
        self.metrics_collector = MetricsCollector(self.config, self.db_manager)
        self.accuracy_analyzer = AccuracyAnalyzer(self.config, self.db_manager)
        self.health_checker = HealthChecker(self.config)
        self.dashboard = MonitoringDashboard(
            self.config, self.db_manager, self.metrics_collector,
            self.accuracy_analyzer, self.health_checker
        )
        
        logger.info("Traffic Prediction Monitor initialized successfully")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.config['logging']
        
        # Create logs directory
        log_dir = Path(log_config['log_file_path']).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format=log_config['log_format'],
            handlers=[
                logging.FileHandler(log_config['log_file_path'].replace('.log', '_monitor.log')),
                logging.StreamHandler()
            ]
        )
    
    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """Run complete monitoring cycle"""
        logger.info("Starting monitoring cycle")
        start_time = time.time()
        
        try:
            # System health check
            health_status = self.health_checker.check_system_health()
            
            # Accuracy analysis
            accuracy_results = self.accuracy_analyzer.analyze_recent_accuracy()
            
            # Record accuracy metrics
            if accuracy_results:
                for accuracy_metrics in accuracy_results:
                    self.metrics_collector.record_accuracy_metrics(accuracy_metrics)
            
            # Generate and save performance report
            report = self.dashboard.generate_performance_report()
            report_path = self.dashboard.save_report(report)
            
            # Flush metrics
            self.metrics_collector.flush_metrics()
            
            processing_time = time.time() - start_time
            
            result = {
                "status": "completed",
                "monitoring_timestamp": datetime.now().isoformat(),
                "processing_time": processing_time,
                "health_status": health_status["overall_status"],
                "accuracy_results_count": len(accuracy_results) if accuracy_results else 0,
                "report_saved": report_path is not None,
                "report_path": report_path
            }
            
            logger.info(f"Monitoring cycle completed: {json.dumps(result, indent=2)}")
            return result
            
        except Exception as e:
            error_msg = f"Monitoring cycle failed: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "status": "failed",
                "error": error_msg,
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'db_manager'):
                self.db_manager.close()
            
            logger.info("Traffic Prediction Monitor cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during monitor cleanup: {str(e)}")


def main():
    """Main execution function"""
    monitor = None
    
    try:
        # Initialize monitor
        monitor = TrafficPredictionMonitor()
        
        # Run monitoring cycle
        result = monitor.run_monitoring_cycle()
        
        # Print results
        print("\n" + "="*70)
        print("MONITORING CYCLE RESULTS")
        print("="*70)
        print(json.dumps(result, indent=2))
        print("="*70)
        
        # Exit code based on result
        if result.get('status') == 'completed':
            exit(0)
        else:
            exit(1)
    
    except Exception as e:
        print(f"Fatal error in monitoring: {str(e)}", file=sys.stderr)
        exit(1)
    
    finally:
        if monitor:
            monitor.cleanup()


if __name__ == "__main__":
    main()