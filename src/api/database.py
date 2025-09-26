"""
Database connection management for FastAPI backend
Handles PostgreSQL connections, session management, and dependency injection
"""

from typing import Generator, Optional
from contextlib import contextmanager, asynccontextmanager
import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.engine import Engine
import asyncpg
import psycopg2

from .config import get_settings
# Base import disabled - using manual table creation only

logger = logging.getLogger(__name__)
settings = get_settings()


class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self):
        self.engine: Optional[Engine] = None
        self.async_engine = None
        self.SessionLocal: Optional[sessionmaker] = None
        self.AsyncSessionLocal = None
        self._initialized = False
    
    def initialize(self):
        """Initialize database connections"""
        if self._initialized:
            return
        
        try:
            # Create synchronous engine
            self.engine = create_engine(
                settings.database_url,
                poolclass=QueuePool,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections after 1 hour
                echo=settings.db_echo
            )
            
            # Create async engine (without poolclass - async engines use AsyncAdaptedQueuePool by default)
            self.async_engine = create_async_engine(
                settings.async_database_url,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=settings.db_echo
            )
            
            # Create session factories
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            self.AsyncSessionLocal = async_sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.async_engine,
                class_=AsyncSession
            )
            
            # Add connection event listeners
            self._setup_connection_events()
            
            self._initialized = True
            logger.info("Database connections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connections: {str(e)}")
            raise
    
    def _setup_connection_events(self):
        """Setup connection event listeners"""
        
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            # PostgreSQL specific settings
            if hasattr(dbapi_connection, 'cursor'):
                cursor = dbapi_connection.cursor()
                cursor.execute("SET search_path = traffic, public")
                cursor.close()
        
        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            logger.debug("Connection checked out from pool")
        
        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            logger.debug("Connection checked in to pool")
    
    async def create_tables(self):
        """Create database tables if they don't exist"""
        try:
            async with self.async_engine.begin() as conn:
                # Create schema first
                from sqlalchemy import text
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS traffic"))
                # Create tables individually to skip problematic indexes
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS traffic.sensors (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        sensor_id VARCHAR(50) NOT NULL UNIQUE,
                        latitude DECIMAL(10, 8) NOT NULL,
                        longitude DECIMAL(11, 8) NOT NULL,
                        road_name VARCHAR(255) NOT NULL,
                        road_type VARCHAR(50),
                        direction VARCHAR(20),
                        lane_count INTEGER,
                        speed_limit INTEGER,
                        city VARCHAR(100),
                        state VARCHAR(50),
                        country VARCHAR(50),
                        installation_date TIMESTAMP WITH TIME ZONE,
                        last_maintenance TIMESTAMP WITH TIME ZONE,
                        status VARCHAR(20),
                        meta_data JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS traffic.traffic_readings (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        sensor_id VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        speed DECIMAL(5, 2),
                        volume INTEGER,
                        occupancy DECIMAL(5, 2),
                        density DECIMAL(7, 2),
                        travel_time DECIMAL(8, 2),
                        weather_condition VARCHAR(50),
                        road_condition VARCHAR(50),
                        quality_score DECIMAL(3, 2),
                        raw_data JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
                
                # Create proper indexes with correct syntax
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_traffic_readings_sensor_timestamp 
                    ON traffic.traffic_readings(sensor_id, timestamp)
                """))
                
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_traffic_readings_recent_by_sensor 
                    ON traffic.traffic_readings(sensor_id, timestamp DESC) 
                    WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '24 hours'
                """))
            logger.info("Database tables created/verified successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {str(e)}")
            raise
    
    async def check_connection(self) -> bool:
        """Check if database connection is healthy"""
        try:
            async with self.async_engine.begin() as conn:
                result = await conn.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False
    
    def get_sync_session(self) -> Session:
        """Get synchronous database session"""
        if not self._initialized:
            self.initialize()
        return self.SessionLocal()
    
    async def get_async_session(self) -> AsyncSession:
        """Get asynchronous database session"""
        if not self._initialized:
            self.initialize()
        return self.AsyncSessionLocal()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations"""
        session = self.get_sync_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    @asynccontextmanager
    async def async_session_scope(self) -> Generator[AsyncSession, None, None]:
        """Provide an async transactional scope around a series of operations"""
        session = await self.get_async_session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def close(self):
        """Close all database connections"""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.engine:
            self.engine.dispose()
        logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for getting database session"""
    session = db_manager.get_sync_session()
    try:
        yield session
    finally:
        session.close()


async def get_async_db() -> Generator[AsyncSession, None, None]:
    """FastAPI dependency for getting async database session"""
    session = await db_manager.get_async_session()
    try:
        yield session
    finally:
        await session.close()


class DatabaseHealthCheck:
    """Database health check utilities"""
    
    @staticmethod
    async def check_database_health() -> dict:
        """Comprehensive database health check"""
        health_status = {
            "database": "unknown",
            "connection_pool": "unknown",
            "schema_access": "unknown",
            "write_access": "unknown",
            "details": {}
        }
        
        try:
            # Check basic connection
            is_connected = await db_manager.check_connection()
            if not is_connected:
                health_status["database"] = "unhealthy"
                return health_status
            
            health_status["database"] = "healthy"
            
            # Check connection pool
            if db_manager.engine:
                pool = db_manager.engine.pool
                health_status["connection_pool"] = "healthy"
                health_status["details"]["pool_size"] = pool.size()
                health_status["details"]["checked_in"] = pool.checkedin()
                health_status["details"]["checked_out"] = pool.checkedout()
            
            # Check schema access
            async with db_manager.async_session_scope() as session:
                # Try to query sensors table
                result = await session.execute("SELECT COUNT(*) FROM traffic.sensors")
                sensor_count = result.scalar()
                health_status["schema_access"] = "healthy"
                health_status["details"]["sensor_count"] = sensor_count
                
                # Check write access (test transaction)
                await session.execute("SELECT 1")
                health_status["write_access"] = "healthy"
        
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            health_status["database"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status


class ConnectionPool:
    """Advanced connection pool management"""
    
    @staticmethod
    def get_pool_stats() -> dict:
        """Get connection pool statistics"""
        if not db_manager.engine:
            return {"error": "Database not initialized"}
        
        pool = db_manager.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }
    
    @staticmethod
    async def test_connection_performance() -> dict:
        """Test connection performance"""
        import time
        
        start_time = time.time()
        try:
            async with db_manager.async_session_scope() as session:
                await session.execute("SELECT 1")
            
            end_time = time.time()
            return {
                "status": "success",
                "response_time_ms": round((end_time - start_time) * 1000, 2)
            }
        except Exception as e:
            end_time = time.time()
            return {
                "status": "error",
                "error": str(e),
                "response_time_ms": round((end_time - start_time) * 1000, 2)
            }


# Initialize database on module import
async def initialize_database():
    """Initialize database connections and tables"""
    try:
        db_manager.initialize()
        await db_manager.create_tables()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise


# Health check utilities
health_checker = DatabaseHealthCheck()
pool_manager = ConnectionPool()