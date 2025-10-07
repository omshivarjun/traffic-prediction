"""
FastAPI Backend Configuration Management
Handles all configuration settings for the traffic prediction API backend
"""

import os
from typing import Optional, List, Dict, Any
from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class DatabaseSettings(BaseSettings):
    """Database connection settings"""
    host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    database: str = Field(default="traffic_db", validation_alias="POSTGRES_DB")
    username: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    password: str = Field(default="casa1234", validation_alias="POSTGRES_PASSWORD")
    pool_size: int = Field(default=20, validation_alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=30, validation_alias="DB_MAX_OVERFLOW")
    echo: bool = Field(default=False, validation_alias="DB_ECHO")
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class KafkaSettings(BaseSettings):
    """Kafka connection settings"""
    bootstrap_servers: List[str] = Field(default=["localhost:9094"], validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    schema_registry_url: str = Field(default="http://localhost:8081", validation_alias="SCHEMA_REGISTRY_URL")
    consumer_group_id: str = Field(default="traffic-api-consumer", validation_alias="KAFKA_CONSUMER_GROUP")
    auto_offset_reset: str = Field(default="latest", validation_alias="KAFKA_AUTO_OFFSET_RESET")
    enable_auto_commit: bool = Field(default=True, validation_alias="KAFKA_ENABLE_AUTO_COMMIT")
    
    # Topic configurations
    traffic_events_topic: str = Field(default="traffic-events", validation_alias="KAFKA_TRAFFIC_EVENTS_TOPIC")
    processed_aggregates_topic: str = Field(default="processed-traffic-aggregates", validation_alias="KAFKA_PROCESSED_AGGREGATES_TOPIC")
    predictions_topic: str = Field(default="traffic-predictions", validation_alias="KAFKA_PREDICTIONS_TOPIC")
    alerts_topic: str = Field(default="traffic-alerts", validation_alias="KAFKA_ALERTS_TOPIC")
    
    @field_validator('bootstrap_servers', mode='before')
    def parse_bootstrap_servers(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v


class HDFSSettings(BaseSettings):
    """HDFS connection settings"""
    namenode_host: str = Field(default="localhost", validation_alias="HDFS_NAMENODE_HOST") 
    namenode_port: int = Field(default=9000, validation_alias="HDFS_NAMENODE_PORT")
    webhdfs_port: int = Field(default=9870, validation_alias="HDFS_WEBHDFS_PORT")
    user: str = Field(default="hadoop", validation_alias="HDFS_USER")
    
    # Paths
    models_path: str = Field(default="/traffic/models", validation_alias="HDFS_MODELS_PATH")
    data_path: str = Field(default="/traffic/data", validation_alias="HDFS_DATA_PATH")
    
    @property
    def url(self) -> str:
        return f"hdfs://{self.namenode_host}:{self.namenode_port}"
    
    @property
    def webhdfs_url(self) -> str:
        return f"http://{self.namenode_host}:{self.webhdfs_port}"


class RedisSettings(BaseSettings):
    """Redis caching settings"""
    host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    port: int = Field(default=6379, validation_alias="REDIS_PORT")
    database: int = Field(default=0, validation_alias="REDIS_DB")
    password: Optional[str] = Field(default=None, validation_alias="REDIS_PASSWORD")
    max_connections: int = Field(default=20, validation_alias="REDIS_MAX_CONNECTIONS")
    
    # Cache settings
    default_ttl: int = Field(default=300, validation_alias="CACHE_DEFAULT_TTL")  # 5 minutes
    traffic_data_ttl: int = Field(default=60, validation_alias="CACHE_TRAFFIC_DATA_TTL")  # 1 minute
    predictions_ttl: int = Field(default=900, validation_alias="CACHE_PREDICTIONS_TTL")  # 15 minutes
    
    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"redis://{self.host}:{self.port}/{self.database}"


class APISettings(BaseSettings):
    """API server settings"""
    title: str = Field(default="Traffic Prediction API", validation_alias="API_TITLE")
    description: str = Field(default="REST API for Traffic Analytics and Predictions", validation_alias="API_DESCRIPTION")
    version: str = Field(default="1.0.0", validation_alias="API_VERSION")
    host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    port: int = Field(default=8000, validation_alias="API_PORT")
    debug: bool = Field(default=False, validation_alias="API_DEBUG")
    reload: bool = Field(default=False, validation_alias="API_RELOAD")
    
    # CORS settings
    allow_origins: List[str] = Field(default=["*"], validation_alias="API_CORS_ORIGINS")
    allow_credentials: bool = Field(default=True, validation_alias="API_CORS_CREDENTIALS")
    allow_methods: List[str] = Field(default=["*"], validation_alias="API_CORS_METHODS")
    allow_headers: List[str] = Field(default=["*"], validation_alias="API_CORS_HEADERS")
    
    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, validation_alias="API_RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, validation_alias="API_RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, validation_alias="API_RATE_LIMIT_WINDOW")
    
    @field_validator('allow_origins', 'allow_methods', 'allow_headers', mode='before')
    def parse_cors_list(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v


class WebSocketSettings(BaseSettings):
    """WebSocket configuration"""
    max_connections: int = Field(default=1000, validation_alias="WS_MAX_CONNECTIONS")
    heartbeat_interval: int = Field(default=30, validation_alias="WS_HEARTBEAT_INTERVAL")
    message_queue_size: int = Field(default=100, validation_alias="WS_MESSAGE_QUEUE_SIZE")
    cleanup_interval: int = Field(default=60, validation_alias="WS_CLEANUP_INTERVAL")
    
    # Streaming settings
    traffic_update_interval: int = Field(default=5, validation_alias="WS_TRAFFIC_UPDATE_INTERVAL")  # seconds
    prediction_update_interval: int = Field(default=60, validation_alias="WS_PREDICTION_UPDATE_INTERVAL")  # seconds
    batch_size: int = Field(default=50, validation_alias="WS_BATCH_SIZE")


class LoggingSettings(BaseSettings):
    """Logging configuration"""
    level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", validation_alias="LOG_FORMAT")
    file_path: Optional[str] = Field(default=None, validation_alias="LOG_FILE_PATH")
    max_bytes: int = Field(default=10485760, validation_alias="LOG_MAX_BYTES")  # 10MB
    backup_count: int = Field(default=5, validation_alias="LOG_BACKUP_COUNT")
    
    # Structured logging
    json_logs: bool = Field(default=False, validation_alias="LOG_JSON_FORMAT")
    request_logging: bool = Field(default=True, validation_alias="LOG_REQUESTS")
    
    @field_validator('level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {valid_levels}')
        return v.upper()


class MonitoringSettings(BaseSettings):
    """Monitoring and metrics settings"""
    enabled: bool = Field(default=True, validation_alias="MONITORING_ENABLED")
    prometheus_enabled: bool = Field(default=True, validation_alias="PROMETHEUS_ENABLED")
    metrics_port: int = Field(default=8001, validation_alias="METRICS_PORT")
    
    # Health check settings
    health_check_interval: int = Field(default=30, validation_alias="HEALTH_CHECK_INTERVAL")
    database_timeout: int = Field(default=5, validation_alias="HEALTH_DB_TIMEOUT")
    kafka_timeout: int = Field(default=5, validation_alias="HEALTH_KAFKA_TIMEOUT")
    hdfs_timeout: int = Field(default=10, validation_alias="HEALTH_HDFS_TIMEOUT")


class SecuritySettings(BaseSettings):
    """Security configuration"""
    secret_key: str = Field(default="your-secret-key-change-in-production", validation_alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(default=24, validation_alias="JWT_EXPIRATION_HOURS")
    
    # API Key settings
    api_key_enabled: bool = Field(default=False, validation_alias="API_KEY_ENABLED")
    api_key_header: str = Field(default="X-API-Key", validation_alias="API_KEY_HEADER")
    
    # HTTPS settings
    ssl_keyfile: Optional[str] = Field(default=None, validation_alias="SSL_KEYFILE")
    ssl_certfile: Optional[str] = Field(default=None, validation_alias="SSL_CERTFILE")


class PredictionSettings(BaseSettings):
    """Prediction service settings"""
    horizons: List[int] = Field(default=[15, 30, 60], validation_alias="PREDICTION_HORIZONS")  # minutes
    max_horizon: int = Field(default=120, validation_alias="PREDICTION_MAX_HORIZON")  # minutes
    confidence_threshold: float = Field(default=0.7, validation_alias="PREDICTION_CONFIDENCE_THRESHOLD")
    
    # Model settings
    default_model: str = Field(default="XGBoost_Traffic_V1", validation_alias="PREDICTION_DEFAULT_MODEL")
    refresh_interval: int = Field(default=3600, validation_alias="PREDICTION_MODEL_REFRESH_INTERVAL")  # seconds
    
    # Caching
    cache_predictions: bool = Field(default=True, validation_alias="PREDICTION_CACHE_ENABLED")
    cache_duration: int = Field(default=300, validation_alias="PREDICTION_CACHE_DURATION")  # seconds
    
    @field_validator('horizons', mode='before')
    def parse_horizons(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v


class Settings(BaseSettings):
    """Main settings class with all configuration in one place"""
    
    # Environment
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    testing: bool = Field(default=False, validation_alias="TESTING")
    
    # Database settings
    db_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    db_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    db_database: str = Field(default="traffic_db", validation_alias="POSTGRES_DB")
    db_username: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    db_password: str = Field(default="casa1234", validation_alias="POSTGRES_PASSWORD")
    db_pool_size: int = Field(default=20, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=30, validation_alias="DB_MAX_OVERFLOW")
    db_echo: bool = Field(default=False, validation_alias="DB_ECHO")
    
    # API settings
    api_title: str = Field(default="Traffic Prediction API", validation_alias="API_TITLE")
    api_description: str = Field(default="REST API for Traffic Analytics and Predictions", validation_alias="API_DESCRIPTION")
    api_version: str = Field(default="1.0.0", validation_alias="API_VERSION")
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    api_debug: bool = Field(default=False, validation_alias="API_DEBUG")
    api_reload: bool = Field(default=False, validation_alias="API_RELOAD")
    
    # CORS settings
    allow_origins: List[str] = Field(default=["*"], validation_alias="API_CORS_ORIGINS")
    allow_credentials: bool = Field(default=True, validation_alias="API_CORS_CREDENTIALS")
    allow_methods: List[str] = Field(default=["*"], validation_alias="API_CORS_METHODS")
    allow_headers: List[str] = Field(default=["*"], validation_alias="API_CORS_HEADERS")
    
    # Logging settings
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    
    # WebSocket settings
    ws_max_connections: int = Field(default=1000, validation_alias="WS_MAX_CONNECTIONS")
    ws_heartbeat_interval: int = Field(default=30, validation_alias="WS_HEARTBEAT_INTERVAL")
    ws_message_queue_size: int = Field(default=100, validation_alias="WS_MESSAGE_QUEUE_SIZE")
    ws_cleanup_interval: int = Field(default=60, validation_alias="WS_CLEANUP_INTERVAL")
    
    # Kafka settings
    kafka_bootstrap_servers: str = Field(default="localhost:9094", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_schema_registry_url: str = Field(default="http://localhost:8081", validation_alias="SCHEMA_REGISTRY_URL")
    
    # Security settings
    jwt_secret_key: str = Field(default="your-secret-key-change-in-production-min-32-chars", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=15, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, validation_alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=100, validation_alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, validation_alias="RATE_LIMIT_PER_HOUR")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_database}"
    
    @property
    def async_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_database}"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Export settings for easy import
settings = get_settings()