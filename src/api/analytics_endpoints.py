"""
FastAPI Backend Analytics and WebSocket Endpoints - Part 2 of main.py
Contains analytics endpoints and WebSocket implementation
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

from fastapi import HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, case

from .database import get_db
from .models import (
    Sensor, TrafficReading, Prediction, ModelMetric, TrafficIncident,
    AnalyticsResponse
)
from .logging_config import api_logger


# =====================================================
# ANALYTICS API ENDPOINTS
# =====================================================

async def get_congestion_analytics(
    hours: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    db: Session = Depends(get_db)
) -> AnalyticsResponse:
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


async def get_pattern_analytics(
    days: int = Query(7, ge=1, le=30, description="Days of data to analyze"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    db: Session = Depends(get_db)
) -> AnalyticsResponse:
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
        
        # Calculate averages
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
        hourly_volumes = [(h, p['avg_volume']) for h, p in hourly_patterns.items() 
                         if p['avg_volume']]
        peak_hour = max(hourly_volumes, key=lambda x: sum(x[1]) / len(x[1]))[0] if hourly_volumes else None
        
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


async def get_trend_analytics(
    days: int = Query(30, ge=7, le=90, description="Days of data to analyze"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    db: Session = Depends(get_db)
) -> AnalyticsResponse:
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

async def websocket_real_time_endpoint(websocket):
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
    from .websocket_manager import websocket_manager
    await websocket_manager.handle_connection(websocket)