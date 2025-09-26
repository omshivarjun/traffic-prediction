"""
FastAPI Backend for Traffic Analytics - Task 14 Implementation
Complete REST API backend for serving traffic data and predictions

Features:
- Traffic data API endpoints (current, historical, sensor-specific, statistics)
- Prediction API endpoints (latest, accuracy, generation)
- Analytics API endpoints (congestion, patterns, trends)
- WebSocket real-time streaming
- Database integration with PostgreSQL
- Kafka streaming integration
- Comprehensive monitoring and health checks
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from uuid import UUID

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query, Path, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from pydantic import BaseModel, Field

from .config import get_settings
from .database import get_db, db_manager, initialize_database, health_checker
from .models import (
    Sensor, TrafficReading, Prediction, ModelMetric, TrafficIncident,
    SensorResponse, TrafficReadingResponse, PredictionResponse, 
    ModelMetricResponse, TrafficIncidentResponse, PaginatedResponse,
    TrafficStatistics, AnalyticsResponse
)
from .kafka_integration import (
    initialize_kafka, shutdown_kafka, traffic_streamer, 
    prediction_streamer, alert_streamer, streaming_health
)
from .logging_config import RequestLoggingMiddleware, api_logger, LoggingConfig
from .websocket_manager import WebSocketManager

# Import ML endpoints
try:
    from .ml_endpoints import router as ml_router
    ML_ENDPOINTS_AVAILABLE = True
except ImportError as e:
    ML_ENDPOINTS_AVAILABLE = False
    api_logger.warning(f"ML endpoints not available: {e}")

# Get settings
settings = get_settings()

# Configure logging on startup
LoggingConfig.log_startup_info()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    api_logger.info("Starting FastAPI Traffic Prediction API")
    
    try:
        # Initialize database
        await initialize_database()
        api_logger.info("Database initialized")
        
        # Initialize Kafka streaming
        await initialize_kafka()
        api_logger.info("Kafka streaming initialized")
        
        # Initialize WebSocket manager
        websocket_manager.initialize()
        api_logger.info("WebSocket manager initialized")
        
        # Setup WebSocket integration with Kafka streamers
        await websocket_manager.setup_kafka_integration(
            traffic_streamer, 
            prediction_streamer, 
            alert_streamer
        )
        api_logger.info("Kafka-WebSocket integration setup completed")
        
        api_logger.info("Application startup completed successfully")
        
    except Exception as e:
        api_logger.error(f"Application startup failed: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    api_logger.info("Shutting down FastAPI Traffic Prediction API")
    
    try:
        await shutdown_kafka()
        await db_manager.close()
        await websocket_manager.close()
        
        LoggingConfig.log_shutdown_info()
        
    except Exception as e:
        api_logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    debug=settings.api_debug,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=settings.allow_credentials,
    allow_methods=settings.allow_methods,
    allow_headers=settings.allow_headers
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Global WebSocket manager
websocket_manager = WebSocketManager()

# Include ML router if available
if ML_ENDPOINTS_AVAILABLE:
    app.include_router(ml_router)
    api_logger.info("ML endpoints included")
else:
    api_logger.warning("ML endpoints not included - ML libraries not available")


# =====================================================
# ROOT AND HEALTH CHECK ENDPOINTS
# =====================================================

@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Traffic Prediction API",
        "version": settings.api_version,
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "endpoints": {
            "traffic": "/api/traffic/*",
            "predictions": "/api/predictions/*", 
            "analytics": "/api/analytics/*",
            "websocket": "/ws/real-time",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Comprehensive health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Database health check
    db_health = await health_checker.check_database_health()
    health_status["checks"]["database"] = db_health
    
    # Kafka health check
    kafka_health = await streaming_health.check_kafka_health()
    health_status["checks"]["kafka"] = kafka_health
    
    # WebSocket health check
    ws_health = websocket_manager.get_health_status()
    health_status["checks"]["websocket"] = ws_health
    
    # Overall status
    unhealthy_checks = [
        check for check in health_status["checks"].values()
        if isinstance(check, dict) and check.get("status") != "healthy"
    ]
    
    if unhealthy_checks:
        health_status["status"] = "unhealthy"
        return JSONResponse(status_code=503, content=health_status)
    
    return health_status


# =====================================================
# TRAFFIC DATA API ENDPOINTS
# =====================================================

@app.get("/api/traffic/current", response_model=List[TrafficReadingResponse], tags=["Traffic Data"])
async def get_current_traffic(
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db)
):
    """Get current traffic data from the last 5 minutes"""
    try:
        # Get traffic data from last 5 minutes
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)
        
        query = db.query(TrafficReading).filter(
            TrafficReading.timestamp >= cutoff_time
        ).order_by(desc(TrafficReading.timestamp))
        
        if sensor_id:
            # Get sensor by sensor_id string
            sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if sensor:
                query = query.filter(TrafficReading.sensor_id == sensor.id)
            else:
                raise HTTPException(status_code=404, detail="Sensor not found")
        
        readings = query.limit(limit).all()
        
        api_logger.info(f"Retrieved {len(readings)} current traffic readings")
        return readings
        
    except Exception as e:
        api_logger.error(f"Error getting current traffic: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/traffic/historical/{date}", response_model=PaginatedResponse, tags=["Traffic Data"])
async def get_historical_traffic(
    date: str = Path(..., description="Date in YYYY-MM-DD format"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=500, description="Page size"),
    db: Session = Depends(get_db)
):
    """Get historical traffic data for a specific date"""
    try:
        # Parse date
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.max.time())
        
        # Build query
        query = db.query(TrafficReading).filter(
            and_(
                TrafficReading.timestamp >= start_time,
                TrafficReading.timestamp <= end_time
            )
        )
        
        if sensor_id:
            sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if sensor:
                query = query.filter(TrafficReading.sensor_id == sensor.id)
            else:
                raise HTTPException(status_code=404, detail="Sensor not found")
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        readings = query.order_by(desc(TrafficReading.timestamp)).offset((page - 1) * size).limit(size).all()
        
        response = PaginatedResponse(
            items=[TrafficReadingResponse.from_orm(reading) for reading in readings],
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
        
        api_logger.info(f"Retrieved {len(readings)} historical traffic readings for {date}")
        return response
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        api_logger.error(f"Error getting historical traffic: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/traffic/sensor/{sensor_id}", response_model=List[TrafficReadingResponse], tags=["Traffic Data"])
async def get_sensor_traffic(
    sensor_id: str = Path(..., description="Sensor ID"),
    hours: int = Query(24, ge=1, le=168, description="Hours of data to retrieve"),
    db: Session = Depends(get_db)
):
    """Get traffic data for a specific sensor"""
    try:
        # Find sensor
        sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor not found")
        
        # Get readings from specified hours
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        readings = db.query(TrafficReading).filter(
            and_(
                TrafficReading.sensor_id == sensor.id,
                TrafficReading.timestamp >= cutoff_time
            )
        ).order_by(desc(TrafficReading.timestamp)).all()
        
        api_logger.info(f"Retrieved {len(readings)} readings for sensor {sensor_id}")
        return readings
        
    except Exception as e:
        api_logger.error(f"Error getting sensor traffic: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/traffic/statistics", response_model=TrafficStatistics, tags=["Traffic Data"])
async def get_traffic_statistics(db: Session = Depends(get_db)):
    """Get traffic system statistics"""
    try:
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        # Count sensors
        sensor_count = db.query(Sensor).count()
        active_sensors = db.query(Sensor).filter(Sensor.status == 'active').count()
        
        # Count readings today
        readings_today = db.query(TrafficReading).filter(
            TrafficReading.timestamp >= today_start
        ).count()
        
        # Average speed and volume today
        avg_stats = db.query(
            func.avg(TrafficReading.speed).label('avg_speed'),
            func.avg(TrafficReading.volume).label('avg_volume')
        ).filter(TrafficReading.timestamp >= today_start).first()
        
        # Count predictions today
        predictions_today = db.query(Prediction).filter(
            Prediction.created_at >= today_start
        ).count()
        
        # Count active incidents
        active_incidents = db.query(TrafficIncident).filter(
            TrafficIncident.status == 'active'
        ).count()
        
        stats = TrafficStatistics(
            sensor_count=sensor_count,
            active_sensors=active_sensors,
            total_readings_today=readings_today,
            avg_speed_today=float(avg_stats.avg_speed) if avg_stats.avg_speed else None,
            avg_volume_today=float(avg_stats.avg_volume) if avg_stats.avg_volume else None,
            predictions_count_today=predictions_today,
            active_incidents=active_incidents,
            last_updated=datetime.utcnow()
        )
        
        api_logger.info("Retrieved traffic statistics")
        return stats
        
    except Exception as e:
        api_logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# PREDICTION API ENDPOINTS  
# =====================================================

@app.get("/api/predictions/latest", response_model=List[PredictionResponse], tags=["Predictions"])
async def get_latest_predictions(
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    horizon: Optional[int] = Query(None, description="Filter by prediction horizon in minutes"),
    limit: int = Query(100, ge=1, le=1000, description="Number of predictions to return"),
    db: Session = Depends(get_db)
):
    """Get latest traffic predictions"""
    try:
        # Get predictions from the last hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        query = db.query(Prediction).filter(
            Prediction.created_at >= cutoff_time
        ).order_by(desc(Prediction.created_at))
        
        if sensor_id:
            sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if sensor:
                query = query.filter(Prediction.sensor_id == sensor.id)
            else:
                raise HTTPException(status_code=404, detail="Sensor not found")
        
        if horizon:
            query = query.filter(Prediction.horizon_minutes == horizon)
        
        predictions = query.limit(limit).all()
        
        api_logger.info(f"Retrieved {len(predictions)} latest predictions")
        return predictions
        
    except Exception as e:
        api_logger.error(f"Error getting latest predictions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/predictions/accuracy", response_model=List[ModelMetricResponse], tags=["Predictions"])
async def get_prediction_accuracy(
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    horizon: Optional[int] = Query(None, description="Filter by prediction horizon"),
    days: int = Query(7, ge=1, le=30, description="Days of metrics to retrieve"),
    db: Session = Depends(get_db)
):
    """Get prediction accuracy metrics"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(ModelMetric).filter(
            ModelMetric.evaluation_date >= cutoff_time
        ).order_by(desc(ModelMetric.evaluation_date))
        
        if model_name:
            query = query.filter(ModelMetric.model_name == model_name)
        
        if horizon:
            query = query.filter(ModelMetric.horizon_minutes == horizon)
        
        metrics = query.all()
        
        api_logger.info(f"Retrieved {len(metrics)} accuracy metrics")
        return metrics
        
    except Exception as e:
        api_logger.error(f"Error getting accuracy metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/predictions/generate", tags=["Predictions"])
async def generate_predictions(
    sensor_id: str = Query(..., description="Sensor ID for prediction"),
    horizons: List[int] = Query([15, 30, 60], description="Prediction horizons in minutes"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Generate on-demand predictions for a sensor"""
    try:
        # Verify sensor exists
        sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor not found")
        
        # Add prediction generation task to background
        background_tasks.add_task(
            _generate_sensor_predictions, 
            sensor_id, 
            horizons
        )
        
        api_logger.info(f"Queued prediction generation for sensor {sensor_id}")
        
        return {
            "message": f"Prediction generation queued for sensor {sensor_id}",
            "sensor_id": sensor_id,
            "horizons": horizons,
            "status": "queued"
        }
        
    except Exception as e:
        api_logger.error(f"Error generating predictions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _generate_sensor_predictions(sensor_id: str, horizons: List[int]):
    """Background task to generate predictions"""
    try:
        # This would call the prediction service
        # For now, just log the request
        api_logger.info(f"Generating predictions for sensor {sensor_id} with horizons {horizons}")
        
        # TODO: Integrate with existing prediction service
        # from ..prediction.prediction_service import PredictionService
        # prediction_service = PredictionService()
        # await prediction_service.generate_predictions(sensor_id, horizons)
        
    except Exception as e:
        api_logger.error(f"Background prediction generation failed: {str(e)}")


# =====================================================
# ANALYTICS API ENDPOINTS
# =====================================================

@app.get("/api/analytics/congestion", response_model=AnalyticsResponse, tags=["Analytics"])
async def get_congestion_analytics(
    hours: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    db: Session = Depends(get_db)
):
    """Get traffic congestion analytics"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Build base query
        query = db.query(
            TrafficReading.timestamp,
            func.avg(TrafficReading.speed).label('avg_speed'),
            func.avg(TrafficReading.volume).label('avg_volume'),
            func.avg(TrafficReading.density).label('avg_density'),
            func.count(TrafficReading.id).label('reading_count')
        ).filter(TrafficReading.timestamp >= cutoff_time)
        
        if sensor_id:
            sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if sensor:
                query = query.filter(TrafficReading.sensor_id == sensor.id)
            else:
                raise HTTPException(status_code=404, detail="Sensor not found")
        
        # Group by hour for time series data
        results = query.group_by(
            func.date_trunc('hour', TrafficReading.timestamp)
        ).order_by(TrafficReading.timestamp).all()
        
        # Convert to data points
        data_points = []
        total_volume = 0
        total_speed = 0
        congested_hours = 0
        
        for result in results:
            congestion_level = "low"
            if result.avg_speed and result.avg_speed < 30:
                congestion_level = "high"
                congested_hours += 1
            elif result.avg_speed and result.avg_speed < 45:
                congestion_level = "medium"
            
            data_point = {
                'timestamp': result.timestamp.isoformat(),
                'avg_speed': float(result.avg_speed) if result.avg_speed else None,
                'avg_volume': float(result.avg_volume) if result.avg_volume else None,
                'avg_density': float(result.avg_density) if result.avg_density else None,
                'congestion_level': congestion_level,
                'reading_count': result.reading_count
            }
            data_points.append(data_point)
            
            if result.avg_volume:
                total_volume += result.avg_volume
            if result.avg_speed:
                total_speed += result.avg_speed
        
        # Calculate summary statistics
        summary = {
            'total_hours_analyzed': len(results),
            'congested_hours': congested_hours,
            'congestion_percentage': (congested_hours / len(results) * 100) if results else 0,
            'avg_speed_overall': total_speed / len(results) if results else None,
            'avg_volume_overall': total_volume / len(results) if results else None
        }
        
        response = AnalyticsResponse(
            metric_name="traffic_congestion",
            time_period=f"last_{hours}_hours",
            data_points=data_points,
            summary=summary,
            generated_at=datetime.utcnow()
        )
        
        api_logger.info(f"Generated congestion analytics for {hours} hours")
        return response
        
    except Exception as e:
        api_logger.error(f"Error generating congestion analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/analytics/patterns", response_model=AnalyticsResponse, tags=["Analytics"])
async def get_pattern_analytics(
    days: int = Query(7, ge=1, le=30, description="Days of data to analyze"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    db: Session = Depends(get_db)
):
    """Get traffic pattern analytics (daily/hourly patterns)"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        # Build base query
        query = db.query(
            func.extract('hour', TrafficReading.timestamp).label('hour'),
            func.extract('dow', TrafficReading.timestamp).label('day_of_week'),  # 0=Sunday
            func.avg(TrafficReading.speed).label('avg_speed'),
            func.avg(TrafficReading.volume).label('avg_volume'),
            func.count(TrafficReading.id).label('reading_count')
        ).filter(TrafficReading.timestamp >= cutoff_time)
        
        if sensor_id:
            sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if sensor:
                query = query.filter(TrafficReading.sensor_id == sensor.id)
            else:
                raise HTTPException(status_code=404, detail="Sensor not found")
        
        # Group by hour and day of week
        results = query.group_by(
            func.extract('hour', TrafficReading.timestamp),
            func.extract('dow', TrafficReading.timestamp)
        ).order_by('hour', 'day_of_week').all()
        
        # Process results into patterns
        hourly_patterns = {}
        daily_patterns = {}
        
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        for result in results:
            hour = int(result.hour)
            dow = int(result.day_of_week)
            day_name = day_names[dow]
            
            # Hourly patterns
            if hour not in hourly_patterns:
                hourly_patterns[hour] = {
                    'hour': hour,
                    'avg_speed': [],
                    'avg_volume': [],
                    'reading_count': 0
                }
            
            if result.avg_speed:
                hourly_patterns[hour]['avg_speed'].append(result.avg_speed)
            if result.avg_volume:
                hourly_patterns[hour]['avg_volume'].append(result.avg_volume)
            hourly_patterns[hour]['reading_count'] += result.reading_count
            
            # Daily patterns
            if day_name not in daily_patterns:
                daily_patterns[day_name] = {
                    'day': day_name,
                    'day_of_week': dow,
                    'avg_speed': [],
                    'avg_volume': [],
                    'reading_count': 0
                }
            
            if result.avg_speed:
                daily_patterns[day_name]['avg_speed'].append(result.avg_speed)
            if result.avg_volume:
                daily_patterns[day_name]['avg_volume'].append(result.avg_volume)
            daily_patterns[day_name]['reading_count'] += result.reading_count
        
        # Calculate averages and create data points
        data_points = []
        
        # Add hourly patterns
        for hour, pattern in hourly_patterns.items():
            avg_speed = sum(pattern['avg_speed']) / len(pattern['avg_speed']) if pattern['avg_speed'] else None
            avg_volume = sum(pattern['avg_volume']) / len(pattern['avg_volume']) if pattern['avg_volume'] else None
            
            data_points.append({
                'type': 'hourly',
                'hour': hour,
                'avg_speed': avg_speed,
                'avg_volume': avg_volume,
                'reading_count': pattern['reading_count']
            })
        
        # Add daily patterns
        for day_name, pattern in daily_patterns.items():
            avg_speed = sum(pattern['avg_speed']) / len(pattern['avg_speed']) if pattern['avg_speed'] else None
            avg_volume = sum(pattern['avg_volume']) / len(pattern['avg_volume']) if pattern['avg_volume'] else None
            
            data_points.append({
                'type': 'daily',
                'day': day_name,
                'day_of_week': pattern['day_of_week'],
                'avg_speed': avg_speed,
                'avg_volume': avg_volume,
                'reading_count': pattern['reading_count']
            })
        
        # Find peak hours
        hourly_volumes = {h: sum(p['avg_volume']) / len(p['avg_volume']) for h, p in hourly_patterns.items() 
                         if p['avg_volume']}
        peak_hour = max(hourly_volumes.keys(), key=lambda h: hourly_volumes[h]) if hourly_volumes else None
        
        summary = {
            'analysis_period_days': days,
            'peak_hour': peak_hour,
            'busiest_day': max(daily_patterns.keys(), 
                             key=lambda d: daily_patterns[d]['reading_count']) if daily_patterns else None,
            'total_data_points': len(data_points)
        }
        
        response = AnalyticsResponse(
            metric_name="traffic_patterns",
            time_period=f"last_{days}_days",
            data_points=data_points,
            summary=summary,
            generated_at=datetime.utcnow()
        )
        
        api_logger.info(f"Generated pattern analytics for {days} days")
        return response
        
    except Exception as e:
        api_logger.error(f"Error generating pattern analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/analytics/trends", response_model=AnalyticsResponse, tags=["Analytics"])
async def get_trend_analytics(
    days: int = Query(30, ge=7, le=90, description="Days of data to analyze"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    db: Session = Depends(get_db)
):
    """Get traffic trend analytics (long-term trends)"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        # Build base query
        query = db.query(
            func.date_trunc('day', TrafficReading.timestamp).label('date'),
            func.avg(TrafficReading.speed).label('avg_speed'),
            func.avg(TrafficReading.volume).label('avg_volume'),
            func.avg(TrafficReading.density).label('avg_density'),
            func.count(TrafficReading.id).label('reading_count')
        ).filter(TrafficReading.timestamp >= cutoff_time)
        
        if sensor_id:
            sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if sensor:
                query = query.filter(TrafficReading.sensor_id == sensor.id)
            else:
                raise HTTPException(status_code=404, detail="Sensor not found")
        
        # Group by day
        results = query.group_by(
            func.date_trunc('day', TrafficReading.timestamp)
        ).order_by('date').all()
        
        # Convert to data points and calculate trends
        data_points = []
        speeds = []
        volumes = []
        
        for result in results:
            data_point = {
                'date': result.date.isoformat(),
                'avg_speed': float(result.avg_speed) if result.avg_speed else None,
                'avg_volume': float(result.avg_volume) if result.avg_volume else None,
                'avg_density': float(result.avg_density) if result.avg_density else None,
                'reading_count': result.reading_count
            }
            data_points.append(data_point)
            
            if result.avg_speed:
                speeds.append(result.avg_speed)
            if result.avg_volume:
                volumes.append(result.avg_volume)
        
        # Calculate trend statistics
        speed_trend = "stable"
        volume_trend = "stable"
        
        if len(speeds) > 1:
            speed_change = (speeds[-1] - speeds[0]) / speeds[0] * 100
            if speed_change > 5:
                speed_trend = "increasing"
            elif speed_change < -5:
                speed_trend = "decreasing"
        
        if len(volumes) > 1:
            volume_change = (volumes[-1] - volumes[0]) / volumes[0] * 100
            if volume_change > 5:
                volume_trend = "increasing"
            elif volume_change < -5:
                volume_trend = "decreasing"
        
        summary = {
            'analysis_period_days': days,
            'speed_trend': speed_trend,
            'volume_trend': volume_trend,
            'avg_speed_overall': sum(speeds) / len(speeds) if speeds else None,
            'avg_volume_overall': sum(volumes) / len(volumes) if volumes else None,
            'total_days_analyzed': len(results)
        }
        
        response = AnalyticsResponse(
            metric_name="traffic_trends",
            time_period=f"last_{days}_days",
            data_points=data_points,
            summary=summary,
            generated_at=datetime.utcnow()
        )
        
        api_logger.info(f"Generated trend analytics for {days} days")
        return response
        
    except Exception as e:
        api_logger.error(f"Error generating trend analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# WEBSOCKET ENDPOINT
# =====================================================

@app.websocket("/ws/real-time")
async def websocket_real_time_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time traffic data streaming
    
    Subscription types:
    - traffic_data: Real-time traffic readings
    - predictions: Traffic predictions  
    - alerts: Traffic alerts and incidents
    - system_status: System health and status
    
    Client message format:
    {
        "type": "subscribe|unsubscribe|pong|get_status",
        "subscription": "traffic_data|predictions|alerts|system_status"
    }
    
    Server message format:
    {
        "type": "traffic_update|prediction_update|alert|system_status|ping|welcome|error",
        "data": {...},
        "timestamp": "ISO-8601-timestamp"
    }
    """
    await websocket_manager.handle_connection(websocket)


# =====================================================
# ADDITIONAL SYSTEM ENDPOINTS
# =====================================================

@app.get("/api/sensors", response_model=List[SensorResponse], tags=["System"])
async def get_sensors(
    status: Optional[str] = Query(None, description="Filter by sensor status"),
    limit: int = Query(100, ge=1, le=1000, description="Number of sensors to return"),
    db: Session = Depends(get_db)
):
    """Get list of traffic sensors"""
    try:
        query = db.query(Sensor)
        
        if status:
            query = query.filter(Sensor.status == status)
        
        sensors = query.limit(limit).all()
        
        api_logger.info(f"Retrieved {len(sensors)} sensors")
        return sensors
        
    except Exception as e:
        api_logger.error(f"Error getting sensors: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/incidents", response_model=List[TrafficIncidentResponse], tags=["System"])
async def get_incidents(
    status: Optional[str] = Query("active", description="Filter by incident status"),
    hours: int = Query(24, ge=1, le=168, description="Hours of incidents to retrieve"),
    db: Session = Depends(get_db)
):
    """Get traffic incidents"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = db.query(TrafficIncident).filter(
            TrafficIncident.start_time >= cutoff_time
        ).order_by(desc(TrafficIncident.start_time))
        
        if status:
            query = query.filter(TrafficIncident.status == status)
        
        incidents = query.all()
        
        api_logger.info(f"Retrieved {len(incidents)} incidents")
        return incidents
        
    except Exception as e:
        api_logger.error(f"Error getting incidents: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )