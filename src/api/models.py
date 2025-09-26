"""
SQLAlchemy Database Models for Traffic Prediction System
Matches the PostgreSQL schema defined in database/init/01_create_schema.sql
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, 
    ForeignKey, Index, CheckConstraint, func, JSON, DECIMAL, text
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.types import UserDefinedType
# Removed geoalchemy2 import - using lat/lng decimal fields instead
from pydantic import BaseModel, Field, validator
from datetime import datetime as dt

# SQLAlchemy base
Base = declarative_base()


class Sensor(Base):
    """Traffic sensor/monitoring point model"""
    __tablename__ = "sensors"
    __table_args__ = {'schema': 'traffic'}
    
    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Basic info
    sensor_id = Column(String(50), unique=True, nullable=False, index=True)
    latitude = Column(DECIMAL(10,8), nullable=False)
    longitude = Column(DECIMAL(11,8), nullable=False)
    road_name = Column(String(255), nullable=False, index=True)
    road_type = Column(String(50), default='highway')
    direction = Column(String(20))
    lane_count = Column(Integer, default=1)
    speed_limit = Column(Integer, default=60)
    
    # Location details
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(50), default='USA')
    
    # Maintenance and status
    installation_date = Column(DateTime(timezone=True), default=func.now())
    last_maintenance = Column(DateTime(timezone=True))
    status = Column(String(20), default='active', index=True)
    
    # Metadata
    meta_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    traffic_readings = relationship("TrafficReading", back_populates="sensor", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="sensor", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("direction IN ('north', 'south', 'east', 'west', 'northbound', 'southbound', 'eastbound', 'westbound')", name='check_direction'),
        CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name='check_status'),
        Index('idx_sensors_location', 'latitude', 'longitude'),
        {'schema': 'traffic'}
    )
    
    def __repr__(self):
        return f"<Sensor(sensor_id='{self.sensor_id}', road='{self.road_name}', status='{self.status}')>"


class TrafficReading(Base):
    """Real-time traffic measurement model"""
    __tablename__ = "traffic_readings"
    __table_args__ = {'schema': 'traffic'}
    
    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign key
    sensor_id = Column(PGUUID(as_uuid=True), ForeignKey('traffic.sensors.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Traffic metrics
    speed = Column(DECIMAL(5,2))  # mph
    volume = Column(Integer)  # vehicles per time period
    occupancy = Column(DECIMAL(5,2))  # percentage
    density = Column(DECIMAL(8,2))  # vehicles per mile
    travel_time = Column(Integer)  # seconds
    
    # Weather conditions
    weather_condition = Column(String(50))
    visibility_km = Column(DECIMAL(4,1))
    temperature_c = Column(DECIMAL(4,1))
    humidity_percent = Column(DECIMAL(5,2))
    wind_speed_kmh = Column(DECIMAL(5,2))
    precipitation_mm = Column(DECIMAL(6,2))
    road_condition = Column(String(30))
    
    # Additional data
    incident_nearby = Column(Boolean, default=False)
    quality_score = Column(DECIMAL(3,2), default=1.0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    sensor = relationship("Sensor", back_populates="traffic_readings")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("speed >= 0 AND speed <= 200", name='check_speed_range'),
        CheckConstraint("volume >= 0", name='check_volume_positive'),
        CheckConstraint("occupancy >= 0 AND occupancy <= 100", name='check_occupancy_range'),
        CheckConstraint("density >= 0", name='check_density_positive'),
        CheckConstraint("travel_time >= 0", name='check_travel_time_positive'),
        CheckConstraint("road_condition IN ('dry', 'wet', 'icy', 'snowy', 'construction')", name='check_road_condition'),
        CheckConstraint("quality_score >= 0 AND quality_score <= 1", name='check_quality_score_range'),
        Index('idx_traffic_readings_sensor_timestamp', 'sensor_id', 'timestamp'),
        Index('idx_traffic_readings_recent_by_sensor', 'sensor_id', 'timestamp'),
        {'schema': 'traffic'}
    )
    
    def __repr__(self):
        return f"<TrafficReading(sensor_id='{self.sensor_id}', timestamp='{self.timestamp}', speed={self.speed})>"


class Prediction(Base):
    """Traffic prediction model"""
    __tablename__ = "predictions"
    __table_args__ = {'schema': 'traffic'}
    
    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign key
    sensor_id = Column(PGUUID(as_uuid=True), ForeignKey('traffic.sensors.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Prediction details
    prediction_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    horizon_minutes = Column(Integer, nullable=False, index=True)
    
    # Predicted values
    predicted_speed = Column(DECIMAL(5,2))
    predicted_volume = Column(Integer) 
    predicted_travel_time = Column(Integer)
    
    # Model info
    confidence_score = Column(DECIMAL(4,3))
    model_name = Column(String(100), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)
    features_used = Column(JSONB)
    
    # Prediction intervals
    prediction_interval_lower = Column(DECIMAL(5,2))
    prediction_interval_upper = Column(DECIMAL(5,2))
    
    # Actual values (for evaluation)
    actual_speed = Column(DECIMAL(5,2))
    actual_volume = Column(Integer)
    prediction_error = Column(DECIMAL(8,4))
    
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    sensor = relationship("Sensor", back_populates="predictions")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("horizon_minutes > 0", name='check_horizon_positive'),
        CheckConstraint("predicted_speed >= 0 AND predicted_speed <= 200", name='check_predicted_speed_range'),
        CheckConstraint("predicted_volume >= 0", name='check_predicted_volume_positive'),
        CheckConstraint("predicted_travel_time >= 0", name='check_predicted_travel_time_positive'),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name='check_confidence_range'),
        Index('idx_predictions_sensor_timestamp', 'sensor_id', 'prediction_timestamp'),
        Index('idx_predictions_recent_by_model', 'model_name', 'prediction_timestamp'),
        {'schema': 'traffic'}
    )
    
    def __repr__(self):
        return f"<Prediction(sensor_id='{self.sensor_id}', horizon={self.horizon_minutes}min, confidence={self.confidence_score})>"


class ModelMetric(Base):
    """Model performance metrics model"""
    __tablename__ = "model_metrics"
    __table_args__ = {'schema': 'traffic'}
    
    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Model identification
    model_name = Column(String(100), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)
    evaluation_date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Metric details
    metric_type = Column(String(50), nullable=False, index=True)  # mae, rmse, mape, r2, etc.
    metric_value = Column(DECIMAL(10,6), nullable=False)
    horizon_minutes = Column(Integer, nullable=False)
    
    # Evaluation context
    sensor_count = Column(Integer)
    sample_size = Column(Integer)
    time_period_start = Column(DateTime(timezone=True))
    time_period_end = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    def __repr__(self):
        return f"<ModelMetric(model='{self.model_name}', metric='{self.metric_type}', value={self.metric_value})>"


class TrafficIncident(Base):
    """Traffic incident model"""
    __tablename__ = "traffic_incidents"
    __table_args__ = {'schema': 'traffic'}
    
    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Incident identification
    incident_id = Column(String(100), unique=True, nullable=False)
    latitude = Column(DECIMAL(10,8), nullable=False)
    longitude = Column(DECIMAL(11,8), nullable=False)
    
    # Incident details
    incident_type = Column(String(50), nullable=False)  # accident, construction, weather, event
    severity = Column(String(20), default='minor')
    description = Column(Text)
    
    # Timing
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    
    # Location details
    affected_lanes = Column(Integer, default=0)
    road_name = Column(String(255))
    direction = Column(String(20))
    city = Column(String(100))
    state = Column(String(50))
    impact_radius_km = Column(DECIMAL(6,2), default=1.0)
    
    # Status and source
    status = Column(String(20), default='active', index=True)
    source = Column(String(50))  # data source identifier
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint("severity IN ('minor', 'moderate', 'major', 'severe')", name='check_severity'),
        CheckConstraint("status IN ('active', 'resolved', 'pending')", name='check_incident_status'),
        Index('idx_incidents_location', 'latitude', 'longitude'),
        Index('idx_incidents_time', 'start_time', 'end_time'),
        {'schema': 'traffic'}
    )
    
    def __repr__(self):
        return f"<TrafficIncident(incident_id='{self.incident_id}', type='{self.incident_type}', severity='{self.severity}')>"


# Pydantic models for API serialization
class SensorResponse(BaseModel):
    """Sensor API response model"""
    id: UUID
    sensor_id: str
    road_name: str
    road_type: Optional[str] = None
    direction: Optional[str] = None
    lane_count: Optional[int] = None
    speed_limit: Optional[int] = None
    city: Optional[str] = None
    state: Optional[str] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class TrafficReadingResponse(BaseModel):
    """Traffic reading API response model"""
    id: UUID
    sensor_id: UUID
    timestamp: datetime
    speed: Optional[float] = None
    volume: Optional[int] = None
    occupancy: Optional[float] = None
    density: Optional[float] = None
    travel_time: Optional[int] = None
    weather_condition: Optional[str] = None
    quality_score: Optional[float] = None
    
    class Config:
        from_attributes = True


class PredictionResponse(BaseModel):
    """Prediction API response model"""
    id: UUID
    sensor_id: UUID
    prediction_timestamp: datetime
    horizon_minutes: int
    predicted_speed: Optional[float] = None
    predicted_volume: Optional[int] = None
    predicted_travel_time: Optional[int] = None
    confidence_score: Optional[float] = None
    model_name: str
    model_version: str
    
    class Config:
        from_attributes = True


class ModelMetricResponse(BaseModel):
    """Model metric API response model"""
    id: UUID
    model_name: str
    model_version: str
    evaluation_date: datetime
    metric_type: str
    metric_value: float
    horizon_minutes: int
    sensor_count: Optional[int] = None
    sample_size: Optional[int] = None
    
    class Config:
        from_attributes = True


class TrafficIncidentResponse(BaseModel):
    """Traffic incident API response model"""
    id: UUID
    incident_id: str
    incident_type: str
    severity: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    road_name: Optional[str] = None
    direction: Optional[str] = None
    status: str
    
    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """Generic paginated response model"""
    items: List[Any]
    total: int
    page: int = 1
    size: int = 50
    pages: int
    
    @validator('pages', always=True)
    def calculate_pages(cls, v, values):
        total = values.get('total', 0)
        size = values.get('size', 50)
        return max(1, (total + size - 1) // size)


class TrafficStatistics(BaseModel):
    """Traffic statistics response model"""
    sensor_count: int
    active_sensors: int
    total_readings_today: int
    avg_speed_today: Optional[float] = None
    avg_volume_today: Optional[float] = None
    predictions_count_today: int
    active_incidents: int
    last_updated: datetime


class AnalyticsResponse(BaseModel):
    """Analytics API response model"""
    metric_name: str
    time_period: str
    data_points: List[Dict[str, Any]]
    summary: Dict[str, Any]
    generated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
