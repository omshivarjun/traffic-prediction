"""
Database Module Initialization for Traffic Prediction System (Task 5.3)
Main entry point for database operations
"""

from .config import DatabaseConfig, get_database_config, set_database_config
from .connection import (
    DatabaseConnectionManager,
    get_connection_manager,
    get_session,
    get_async_session,
    health_check,
    async_health_check,
    close_connections
)

# Temporarily disabled to avoid problematic model imports
# from .models import (
#     Base,
#     Sensor,
#     TrafficReading,
#     Prediction,
#     ModelMetric,
#     TrafficIncident
# )

from .crud import (
    SensorCRUD,
    TrafficReadingCRUD,
    PredictionCRUD,
    ModelMetricCRUD,
    DatabaseOperations,
    db_ops
)

# Version information
__version__ = "1.0.0"

# Main exports
__all__ = [
    # Configuration
    'DatabaseConfig',
    'get_database_config',
    'set_database_config',
    
    # Connection management
    'DatabaseConnectionManager',
    'get_connection_manager',
    'get_session',
    'get_async_session',
    'health_check',
    'async_health_check',
    'close_connections',
    
    # Models
    'Base',
    'Sensor',
    'TrafficReading',
    'Prediction',
    'ModelMetric',
    'TrafficIncident',
    
    # CRUD operations
    'SensorCRUD',
    'TrafficReadingCRUD',
    'PredictionCRUD',
    'ModelMetricCRUD',
    'DatabaseOperations',
    'db_ops'
]


def initialize_database(config: DatabaseConfig = None) -> DatabaseConnectionManager:
    """
    Initialize the database connection and create tables if needed.
    
    Args:
        config: Database configuration. If None, uses environment variables.
    
    Returns:
        DatabaseConnectionManager instance
    """
    if config:
        set_database_config(config)
    
    manager = get_connection_manager()
    
    try:
        # Test connection
        if not health_check():
            raise ConnectionError("Failed to connect to database")
        
        # Create tables if they don't exist
        manager.create_tables()
        
        return manager
        
    except Exception as e:
        raise RuntimeError(f"Database initialization failed: {e}")


def get_db_stats():
    """Get database statistics and health information"""
    return db_ops.get_system_health()