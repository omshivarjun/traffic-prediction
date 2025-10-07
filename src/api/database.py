"""
Database connection management for FastAPI backend
Handles PostgreSQL connections, session management, and dependency injection
"""

from typing import Generator, Optional
from contextlib import contextmanager, asynccontextmanager
import logging

from sqlalchemy import create_engine, event, text
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
        """Create database tables if they don't exist - using SQL schema file instead"""
        try:
            # The database schema is managed by the SQL initialization script
            # in database/init/01_create_schema.sql
            # This function just verifies the schema exists
            async with self.async_engine.begin() as conn:
                # Ensure uuid-ossp extension is enabled
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
                
                # Ensure schema exists
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS traffic"))
                
                # Set search path
                await conn.execute(text("SET search_path = traffic, public"))
                
                # Verify tables exist - if not, they should be created by the SQL init script
                result = await conn.execute(text("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'traffic' AND table_name = 'sensors'
                """))
                table_count = result.scalar()
                
                if table_count == 0:
                    logger.warning("Traffic schema tables not found. They should be created by SQL init script.")
                    logger.info("Run the SQL script: database/init/01_create_schema.sql")
                else:
                    logger.info(f"Database schema verified - found {table_count} core tables")
                    
            logger.info("Database tables verified successfully")
        except Exception as e:
            logger.error(f"Failed to verify database tables: {str(e)}")
            # Don't raise - allow app to start even if tables don't exist yet
            logger.warning("Application starting without database schema verification")
    
    async def check_connection(self) -> bool:
        """Check if database connection is healthy"""
        try:
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
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
            "status": "unknown",
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
                health_status["status"] = "unhealthy"
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
                result = await session.execute(text("SELECT COUNT(*) FROM traffic.sensors"))
                sensor_count = result.scalar()
                health_status["schema_access"] = "healthy"
                health_status["details"]["sensor_count"] = sensor_count
                
                # Check write access (test transaction)
                await session.execute(text("SELECT 1"))
                health_status["write_access"] = "healthy"
            
            # Set overall status to healthy if all checks passed
            health_status["status"] = "healthy"
        
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            health_status["database"] = "unhealthy"
            health_status["status"] = "unhealthy"
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