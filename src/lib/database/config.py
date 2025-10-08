"""
Database Configuration for Traffic Prediction System (Task 5.3)
PostgreSQL connection settings and environment management
"""

import os
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str = "localhost"
    port: int = 5432
    database: str = "traffic_db"
    username: str = "postgres"
    password: str = "casa1234"
    schema: str = "traffic"
    
    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # 1 hour
    
    # Connection settings
    connect_timeout: int = 10
    statement_timeout: int = 30000  # 30 seconds
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create configuration from environment variables"""
        return cls(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'traffic_db'),
            username=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'casa1234'),
            schema=os.getenv('POSTGRES_SCHEMA', 'traffic'),
            pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '20')),
            pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', '30')),
            pool_recycle=int(os.getenv('DB_POOL_RECYCLE', '3600')),
            connect_timeout=int(os.getenv('DB_CONNECT_TIMEOUT', '10')),
            statement_timeout=int(os.getenv('DB_STATEMENT_TIMEOUT', '30000'))
        )
    
    @property
    def database_url(self) -> str:
        """Get SQLAlchemy database URL"""
        password_encoded = quote_plus(self.password)
        return (
            f"postgresql+psycopg2://{self.username}:{password_encoded}"
            f"@{self.host}:{self.port}/{self.database}"
        )
    
    @property
    def async_database_url(self) -> str:
        """Get async SQLAlchemy database URL"""
        password_encoded = quote_plus(self.password)
        return (
            f"postgresql+asyncpg://{self.username}:{password_encoded}"
            f"@{self.host}:{self.port}/{self.database}"
        )


# Default configuration
default_config = DatabaseConfig.from_env()


def get_database_config() -> DatabaseConfig:
    """Get the current database configuration"""
    return default_config


def set_database_config(config: DatabaseConfig) -> None:
    """Set the database configuration"""
    global default_config
    default_config = config