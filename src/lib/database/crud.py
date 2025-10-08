"""
CRUD Operations for Traffic Prediction System (Task 5.3)
Database operations for sensors, traffic readings, predictions, and incidents
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# from .models import Sensor, TrafficReading, Prediction, ModelMetric, TrafficIncident  # Temporarily disabled
from .connection import get_session, get_async_session


logger = logging.getLogger(__name__)


class SensorCRUD:
    """CRUD operations for traffic sensors"""
    
    @staticmethod
    def create_sensor(
        sensor_id: str,
        location_lat: float,
        location_lon: float,
        road_name: str,
        road_type: str = 'highway',
        direction: Optional[str] = None,
        lane_count: int = 1,
        speed_limit: int = 60,
        city: Optional[str] = None,
        state: Optional[str] = None,
        **kwargs
    ) -> Sensor:
        """Create a new traffic sensor"""
        with get_session() as session:
            try:
                # Create PostGIS point from lat/lon
                location_wkt = f"POINT({location_lon} {location_lat})"
                
                sensor = Sensor(
                    sensor_id=sensor_id,
                    location=func.ST_GeogFromText(location_wkt),
                    road_name=road_name,
                    road_type=road_type,
                    direction=direction,
                    lane_count=lane_count,
                    speed_limit=speed_limit,
                    city=city,
                    state=state,
                    **kwargs
                )
                
                session.add(sensor)
                session.flush()  # Get the ID without committing
                session.refresh(sensor)
                
                logger.info(f"Created sensor: {sensor_id} on {road_name}")
                return sensor
                
            except IntegrityError as e:
                logger.error(f"Sensor {sensor_id} already exists: {e}")
                raise ValueError(f"Sensor with ID {sensor_id} already exists")
            except Exception as e:
                logger.error(f"Failed to create sensor {sensor_id}: {e}")
                raise
    
    @staticmethod
    def get_sensor_by_id(sensor_id: str) -> Optional[Sensor]:
        """Get sensor by sensor_id"""
        with get_session() as session:
            return session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
    
    @staticmethod
    def get_sensors_by_road(road_name: str) -> List[Sensor]:
        """Get all sensors on a specific road"""
        with get_session() as session:
            return session.query(Sensor).filter(Sensor.road_name == road_name).all()
    
    @staticmethod
    def get_active_sensors() -> List[Sensor]:
        """Get all active sensors"""
        with get_session() as session:
            return session.query(Sensor).filter(Sensor.status == 'active').all()
    
    @staticmethod
    def get_sensors_near_location(lat: float, lon: float, radius_km: float = 5.0) -> List[Tuple[Sensor, float]]:
        """Get sensors within radius of a location with distances"""
        with get_session() as session:
            location_wkt = f"POINT({lon} {lat})"
            
            query = session.query(
                Sensor,
                func.ST_Distance(
                    Sensor.location,
                    func.ST_GeogFromText(location_wkt)
                ).label('distance_m')
            ).filter(
                func.ST_DWithin(
                    Sensor.location,
                    func.ST_GeogFromText(location_wkt),
                    radius_km * 1000  # Convert km to meters
                )
            ).order_by('distance_m')
            
            return [(sensor, distance / 1000) for sensor, distance in query.all()]  # Convert back to km
    
    @staticmethod
    def update_sensor_status(sensor_id: str, status: str) -> bool:
        """Update sensor status"""
        with get_session() as session:
            sensor = session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if sensor:
                sensor.status = status
                sensor.updated_at = datetime.utcnow()
                logger.info(f"Updated sensor {sensor_id} status to {status}")
                return True
            return False
    
    @staticmethod
    def delete_sensor(sensor_id: str) -> bool:
        """Delete sensor and all related data"""
        with get_session() as session:
            sensor = session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if sensor:
                session.delete(sensor)  # Cascade will handle related records
                logger.warning(f"Deleted sensor {sensor_id} and all related data")
                return True
            return False


class TrafficReadingCRUD:
    """CRUD operations for traffic readings"""
    
    @staticmethod
    def create_reading(
        sensor_id: str,
        timestamp: datetime,
        speed: Optional[float] = None,
        volume: Optional[int] = None,
        occupancy: Optional[float] = None,
        **kwargs
    ) -> TrafficReading:
        """Create a new traffic reading"""
        with get_session() as session:
            # Get sensor UUID from sensor_id
            sensor = session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if not sensor:
                raise ValueError(f"Sensor {sensor_id} not found")
            
            reading = TrafficReading(
                sensor_id=sensor.id,
                timestamp=timestamp,
                speed=Decimal(str(speed)) if speed is not None else None,
                volume=volume,
                occupancy=Decimal(str(occupancy)) if occupancy is not None else None,
                **kwargs
            )
            
            session.add(reading)
            session.flush()
            session.refresh(reading)
            
            return reading
    
    @staticmethod
    def get_latest_reading(sensor_id: str) -> Optional[TrafficReading]:
        """Get the most recent reading for a sensor"""
        with get_session() as session:
            sensor = session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if not sensor:
                return None
                
            return session.query(TrafficReading).filter(
                TrafficReading.sensor_id == sensor.id
            ).order_by(desc(TrafficReading.timestamp)).first()
    
    @staticmethod
    def get_readings_in_timerange(
        sensor_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[TrafficReading]:
        """Get readings for a sensor within a time range"""
        with get_session() as session:
            sensor = session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if not sensor:
                return []
                
            return session.query(TrafficReading).filter(
                and_(
                    TrafficReading.sensor_id == sensor.id,
                    TrafficReading.timestamp >= start_time,
                    TrafficReading.timestamp <= end_time
                )
            ).order_by(TrafficReading.timestamp).all()
    
    @staticmethod
    def get_recent_readings(sensor_id: str, hours: int = 24) -> List[TrafficReading]:
        """Get recent readings for a sensor"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        return TrafficReadingCRUD.get_readings_in_timerange(sensor_id, start_time, end_time)
    
    @staticmethod
    def get_average_speed_by_hour(sensor_id: str, date: datetime.date) -> List[Dict]:
        """Get average speed by hour for a specific date"""
        with get_session() as session:
            sensor = session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if not sensor:
                return []
            
            start_date = datetime.combine(date, datetime.min.time())
            end_date = start_date + timedelta(days=1)
            
            query = session.query(
                func.extract('hour', TrafficReading.timestamp).label('hour'),
                func.avg(TrafficReading.speed).label('avg_speed'),
                func.count(TrafficReading.id).label('reading_count')
            ).filter(
                and_(
                    TrafficReading.sensor_id == sensor.id,
                    TrafficReading.timestamp >= start_date,
                    TrafficReading.timestamp < end_date,
                    TrafficReading.speed.isnot(None)
                )
            ).group_by(func.extract('hour', TrafficReading.timestamp))
            
            return [
                {
                    'hour': int(row.hour),
                    'avg_speed': float(row.avg_speed) if row.avg_speed else None,
                    'reading_count': row.reading_count
                }
                for row in query.all()
            ]


class PredictionCRUD:
    """CRUD operations for traffic predictions"""
    
    @staticmethod
    def create_prediction(
        sensor_id: str,
        prediction_timestamp: datetime,
        horizon_minutes: int,
        model_name: str,
        model_version: str,
        predicted_speed: Optional[float] = None,
        predicted_volume: Optional[int] = None,
        confidence_score: Optional[float] = None,
        **kwargs
    ) -> Prediction:
        """Create a new traffic prediction"""
        with get_session() as session:
            sensor = session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if not sensor:
                raise ValueError(f"Sensor {sensor_id} not found")
            
            prediction = Prediction(
                sensor_id=sensor.id,
                prediction_timestamp=prediction_timestamp,
                horizon_minutes=horizon_minutes,
                model_name=model_name,
                model_version=model_version,
                predicted_speed=Decimal(str(predicted_speed)) if predicted_speed is not None else None,
                predicted_volume=predicted_volume,
                confidence_score=Decimal(str(confidence_score)) if confidence_score is not None else None,
                **kwargs
            )
            
            session.add(prediction)
            session.flush()
            session.refresh(prediction)
            
            return prediction
    
    @staticmethod
    def get_current_predictions(sensor_id: str, horizon_hours: int = 6) -> List[Prediction]:
        """Get current predictions for a sensor"""
        with get_session() as session:
            sensor = session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
            if not sensor:
                return []
            
            now = datetime.utcnow()
            future_time = now + timedelta(hours=horizon_hours)
            
            return session.query(Prediction).filter(
                and_(
                    Prediction.sensor_id == sensor.id,
                    Prediction.prediction_timestamp >= now,
                    Prediction.prediction_timestamp <= future_time
                )
            ).order_by(Prediction.prediction_timestamp).all()
    
    @staticmethod
    def update_prediction_with_actual(
        prediction_id: uuid.UUID,
        actual_speed: Optional[float] = None,
        actual_volume: Optional[int] = None
    ) -> bool:
        """Update prediction with actual values for evaluation"""
        with get_session() as session:
            prediction = session.query(Prediction).filter(Prediction.id == prediction_id).first()
            if not prediction:
                return False
            
            if actual_speed is not None:
                prediction.actual_speed = Decimal(str(actual_speed))
                if prediction.predicted_speed:
                    prediction.prediction_error = abs(
                        Decimal(str(actual_speed)) - prediction.predicted_speed
                    )
            
            if actual_volume is not None:
                prediction.actual_volume = actual_volume
            
            return True


class ModelMetricCRUD:
    """CRUD operations for model metrics"""
    
    @staticmethod
    def record_metric(
        model_name: str,
        model_version: str,
        metric_type: str,
        metric_value: float,
        horizon_minutes: int,
        **kwargs
    ) -> ModelMetric:
        """Record a model performance metric"""
        with get_session() as session:
            metric = ModelMetric(
                model_name=model_name,
                model_version=model_version,
                evaluation_date=datetime.utcnow(),
                metric_type=metric_type,
                metric_value=Decimal(str(metric_value)),
                horizon_minutes=horizon_minutes,
                **kwargs
            )
            
            session.add(metric)
            session.flush()
            session.refresh(metric)
            
            return metric
    
    @staticmethod
    def get_latest_metrics(model_name: str, model_version: str) -> List[ModelMetric]:
        """Get the latest metrics for a model"""
        with get_session() as session:
            return session.query(ModelMetric).filter(
                and_(
                    ModelMetric.model_name == model_name,
                    ModelMetric.model_version == model_version
                )
            ).order_by(desc(ModelMetric.evaluation_date)).limit(10).all()


class DatabaseOperations:
    """High-level database operations combining multiple CRUD classes"""
    
    sensor = SensorCRUD
    reading = TrafficReadingCRUD
    prediction = PredictionCRUD
    metric = ModelMetricCRUD
    
    @staticmethod
    def get_system_health() -> Dict[str, Any]:
        """Get system health statistics"""
        with get_session() as session:
            try:
                # Count records in each table
                sensor_count = session.query(Sensor).count()
                active_sensor_count = session.query(Sensor).filter(Sensor.status == 'active').count()
                
                # Recent data counts (last 24 hours)
                since_yesterday = datetime.utcnow() - timedelta(days=1)
                recent_readings = session.query(TrafficReading).filter(
                    TrafficReading.timestamp >= since_yesterday
                ).count()
                
                recent_predictions = session.query(Prediction).filter(
                    Prediction.created_at >= since_yesterday
                ).count()
                
                return {
                    'sensors': {
                        'total': sensor_count,
                        'active': active_sensor_count
                    },
                    'readings_24h': recent_readings,
                    'predictions_24h': recent_predictions,
                    'timestamp': datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Failed to get system health: {e}")
                return {'error': str(e)}


# Export the main operations class
db_ops = DatabaseOperations()

__all__ = [
    'SensorCRUD',
    'TrafficReadingCRUD', 
    'PredictionCRUD',
    'ModelMetricCRUD',
    'DatabaseOperations',
    'db_ops'
]