"""
Database Connection Manager for Traffic Prediction System (Task 5.3)
Handles PostgreSQL connections, connection pooling, and session management
"""

import logging
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Optional
import asyncio
from threading import Lock

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError

from .config import DatabaseConfig, get_database_config
# from .models import Base  # Temporarily disabled


logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """Manages database connections and sessions for the traffic prediction system"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or get_database_config()
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None
        self._lock = Lock()
        self._initialized = False
    
    def _create_engine(self):
        """Create the SQLAlchemy engine with connection pooling"""
        if self._engine is not None:
            return self._engine
            
        engine_kwargs = {
            'url': self.config.database_url,
            'poolclass': QueuePool,
            'pool_size': self.config.pool_size,
            'max_overflow': self.config.max_overflow,
            'pool_timeout': self.config.pool_timeout,
            'pool_recycle': self.config.pool_recycle,
            'pool_pre_ping': True,  # Verify connections before use
            'connect_args': {
                'connect_timeout': self.config.connect_timeout,
                'options': f'-c search_path={self.config.schema},public'
            },
            'echo': False  # Set to True for SQL debugging
        }
        
        try:
            self._engine = create_engine(**engine_kwargs)
            
            # Add event listeners for connection handling
            @event.listens_for(self._engine, "connect")
            def set_statement_timeout(dbapi_connection, connection_record):
                """Set statement timeout for each connection"""
                with dbapi_connection.cursor() as cursor:
                    cursor.execute(f"SET statement_timeout = {self.config.statement_timeout}")
            
            logger.info(f"Database engine created: {self.config.host}:{self.config.port}/{self.config.database}")
            return self._engine
            
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}")
            raise
    
    def _create_async_engine(self):
        """Create the async SQLAlchemy engine"""
        if self._async_engine is not None:
            return self._async_engine
            
        engine_kwargs = {
            'url': self.config.async_database_url,
            'pool_size': self.config.pool_size,
            'max_overflow': self.config.max_overflow,
            'pool_timeout': self.config.pool_timeout,
            'pool_recycle': self.config.pool_recycle,
            'pool_pre_ping': True,
            'connect_args': {
                'command_timeout': self.config.connect_timeout,
                'server_settings': {
                    'search_path': f'{self.config.schema},public',
                    'statement_timeout': str(self.config.statement_timeout)
                }
            }
        }
        
        try:
            self._async_engine = create_async_engine(**engine_kwargs)
            logger.info(f"Async database engine created: {self.config.host}:{self.config.port}/{self.config.database}")
            return self._async_engine
            
        except Exception as e:
            logger.error(f"Failed to create async database engine: {e}")
            raise
    
    def initialize(self):
        """Initialize the database connection manager"""
        with self._lock:
            if self._initialized:
                return
                
            try:
                # Create engines
                engine = self._create_engine()
                async_engine = self._create_async_engine()
                
                # Create session factories
                self._session_factory = sessionmaker(
                    bind=engine,
                    expire_on_commit=False,
                    autoflush=True,
                    autocommit=False
                )
                
                self._async_session_factory = async_sessionmaker(
                    bind=async_engine,
                    expire_on_commit=False,
                    autoflush=True,
                    autocommit=False
                )
                
                self._initialized = True
                logger.info("Database connection manager initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize database connection manager: {e}")
                raise
    
    def health_check(self) -> bool:
        """Check if the database connection is healthy"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def async_health_check(self) -> bool:
        """Async health check for the database connection"""
        try:
            async with self.get_async_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Async database health check failed: {e}")
            return False
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup"""
        if not self._initialized:
            self.initialize()
            
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session with automatic cleanup"""
        if not self._initialized:
            self.initialize()
            
        session = self._async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Async database session error: {e}")
            raise
        finally:
            await session.close()
    
    def create_tables(self):
        """Create all database tables"""
        if not self._initialized:
            self.initialize()
            
        try:
            Base.metadata.create_all(bind=self._engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        if not self._initialized:
            self.initialize()
            
        try:
            Base.metadata.drop_all(bind=self._engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    def close(self):
        """Close all database connections"""
        if self._engine:
            self._engine.dispose()
            logger.info("Database engine disposed")
        
        if self._async_engine:
            asyncio.create_task(self._async_engine.dispose())
            logger.info("Async database engine disposed")
        
        self._initialized = False


# Global connection manager instance
_connection_manager: Optional[DatabaseConnectionManager] = None
_manager_lock = Lock()


def get_connection_manager() -> DatabaseConnectionManager:
    """Get the global database connection manager instance"""
    global _connection_manager
    
    if _connection_manager is None:
        with _manager_lock:
            if _connection_manager is None:
                _connection_manager = DatabaseConnectionManager()
                _connection_manager.initialize()
    
    return _connection_manager


def get_session() -> Generator[Session, None, None]:
    """Get a database session (convenience function)"""
    return get_connection_manager().get_session()


def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session (convenience function)"""
    return get_connection_manager().get_async_session()


def health_check() -> bool:
    """Check database health (convenience function)"""
    return get_connection_manager().health_check()


async def async_health_check() -> bool:
    """Async database health check (convenience function)"""
    return await get_connection_manager().async_health_check()


def close_connections():
    """Close all database connections"""
    global _connection_manager
    if _connection_manager:
        _connection_manager.close()
        _connection_manager = None