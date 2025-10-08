"""
Database Migration System for Traffic Prediction System (Task 5.4)
Handles schema versioning, migrations, and rollbacks
"""

import os
import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from .config import get_database_config


logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Custom exception for migration errors"""
    pass


class Migration:
    """Represents a single database migration"""
    
    def __init__(self, version: str, name: str, up_sql: str, down_sql: str = None):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.timestamp = datetime.utcnow()
    
    def __repr__(self):
        return f"<Migration(version='{self.version}', name='{self.name}')>"


class MigrationManager:
    """Manages database schema migrations"""
    
    def __init__(self, migrations_dir: str = None):
        self.config = get_database_config()
        self.migrations_dir = Path(migrations_dir or "database/migrations")
        self.migrations_table = "schema_migrations"
        self._ensure_migrations_dir()
    
    def _ensure_migrations_dir(self):
        """Ensure migrations directory exists"""
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.username,
            password=self.config.password,
            connect_timeout=self.config.connect_timeout
        )
    
    def _create_migrations_table(self):
        """Create the schema_migrations table if it doesn't exist"""
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.migrations_table} (
            version VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            execution_time_ms INTEGER,
            checksum VARCHAR(64)
        );
        
        CREATE INDEX IF NOT EXISTS idx_migrations_applied_at 
        ON {self.migrations_table}(applied_at DESC);
        """
        
        with self._get_connection() as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cursor:
                cursor.execute(sql)
    
    def _get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT version FROM {self.migrations_table} ORDER BY version")
                return [row[0] for row in cursor.fetchall()]
    
    def _calculate_checksum(self, content: str) -> str:
        """Calculate MD5 checksum of migration content"""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()
    
    def _parse_migration_file(self, file_path: Path) -> Migration:
        """Parse a migration file"""
        content = file_path.read_text(encoding='utf-8')
        
        # Extract version and name from filename
        # Format: V001__create_initial_schema.sql
        filename = file_path.stem
        match = re.match(r'V(\d+)__(.+)', filename)
        if not match:
            raise MigrationError(f"Invalid migration filename format: {filename}")
        
        version = match.group(1)
        name = match.group(2).replace('_', ' ')
        
        # Split up and down migrations if present
        up_sql = content
        down_sql = None
        
        # Look for -- DOWN marker
        if '-- DOWN' in content:
            parts = content.split('-- DOWN', 1)
            up_sql = parts[0].strip()
            down_sql = parts[1].strip() if len(parts) > 1 else None
        
        return Migration(version, name, up_sql, down_sql)
    
    def discover_migrations(self) -> List[Migration]:
        """Discover all migration files"""
        migrations = []
        
        for file_path in sorted(self.migrations_dir.glob("V*.sql")):
            try:
                migration = self._parse_migration_file(file_path)
                migrations.append(migration)
            except Exception as e:
                logger.error(f"Failed to parse migration {file_path}: {e}")
                raise MigrationError(f"Invalid migration file {file_path}: {e}")
        
        return migrations
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations"""
        all_migrations = self.discover_migrations()
        applied_versions = set(self._get_applied_migrations())
        
        return [m for m in all_migrations if m.version not in applied_versions]
    
    def apply_migration(self, migration: Migration) -> Dict[str, any]:
        """Apply a single migration"""
        start_time = datetime.utcnow()
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Execute the migration
                    cursor.execute(migration.up_sql)
                    
                    # Record the migration
                    execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    checksum = self._calculate_checksum(migration.up_sql)
                    
                    cursor.execute(f"""
                        INSERT INTO {self.migrations_table} 
                        (version, name, applied_at, execution_time_ms, checksum)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (migration.version, migration.name, start_time, execution_time, checksum))
                    
                    conn.commit()
            
            result = {
                'version': migration.version,
                'name': migration.name,
                'status': 'success',
                'execution_time_ms': execution_time
            }
            
            logger.info(f"Applied migration {migration.version}: {migration.name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to apply migration {migration.version}: {e}")
            raise MigrationError(f"Migration {migration.version} failed: {e}")
    
    def rollback_migration(self, migration: Migration) -> Dict[str, any]:
        """Rollback a single migration"""
        if not migration.down_sql:
            raise MigrationError(f"Migration {migration.version} has no rollback SQL")
        
        start_time = datetime.utcnow()
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Execute the rollback
                    cursor.execute(migration.down_sql)
                    
                    # Remove migration record
                    cursor.execute(f"DELETE FROM {self.migrations_table} WHERE version = %s", 
                                 (migration.version,))
                    
                    conn.commit()
            
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            result = {
                'version': migration.version,
                'name': migration.name,
                'status': 'rolled_back',
                'execution_time_ms': execution_time
            }
            
            logger.info(f"Rolled back migration {migration.version}: {migration.name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to rollback migration {migration.version}: {e}")
            raise MigrationError(f"Migration rollback {migration.version} failed: {e}")
    
    def migrate(self) -> List[Dict[str, any]]:
        """Apply all pending migrations"""
        self._create_migrations_table()
        
        pending = self.get_pending_migrations()
        if not pending:
            logger.info("No pending migrations to apply")
            return []
        
        results = []
        for migration in pending:
            result = self.apply_migration(migration)
            results.append(result)
        
        logger.info(f"Applied {len(results)} migrations successfully")
        return results
    
    def rollback(self, steps: int = 1) -> List[Dict[str, any]]:
        """Rollback the last N migrations"""
        applied_versions = self._get_applied_migrations()
        if not applied_versions:
            logger.info("No migrations to rollback")
            return []
        
        # Get the migrations to rollback (in reverse order)
        versions_to_rollback = applied_versions[-steps:]
        all_migrations = {m.version: m for m in self.discover_migrations()}
        
        results = []
        for version in reversed(versions_to_rollback):
            if version not in all_migrations:
                raise MigrationError(f"Migration file for version {version} not found")
            
            migration = all_migrations[version]
            result = self.rollback_migration(migration)
            results.append(result)
        
        logger.info(f"Rolled back {len(results)} migrations successfully")
        return results
    
    def status(self) -> Dict[str, any]:
        """Get migration status information"""
        try:
            self._create_migrations_table()
            
            all_migrations = self.discover_migrations()
            applied_versions = set(self._get_applied_migrations())
            
            applied = [m for m in all_migrations if m.version in applied_versions]
            pending = [m for m in all_migrations if m.version not in applied_versions]
            
            return {
                'total_migrations': len(all_migrations),
                'applied_count': len(applied),
                'pending_count': len(pending),
                'applied_migrations': [
                    {'version': m.version, 'name': m.name} for m in applied
                ],
                'pending_migrations': [
                    {'version': m.version, 'name': m.name} for m in pending
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            return {'error': str(e)}
    
    def create_migration(self, name: str, up_sql: str, down_sql: str = None) -> Path:
        """Create a new migration file"""
        # Find next version number
        existing_migrations = self.discover_migrations()
        if existing_migrations:
            last_version = int(existing_migrations[-1].version)
            new_version = f"{last_version + 1:03d}"
        else:
            new_version = "001"
        
        # Create filename
        clean_name = re.sub(r'[^\w\s-]', '', name).strip()
        clean_name = re.sub(r'[-\s]+', '_', clean_name).lower()
        filename = f"V{new_version}__{clean_name}.sql"
        
        # Create file content
        content = f"-- Migration: {name}\n-- Version: {new_version}\n-- Created: {datetime.utcnow().isoformat()}\n\n"
        content += up_sql
        
        if down_sql:
            content += f"\n\n-- DOWN\n-- Rollback SQL for migration {new_version}\n\n"
            content += down_sql
        
        # Write file
        file_path = self.migrations_dir / filename
        file_path.write_text(content, encoding='utf-8')
        
        logger.info(f"Created migration: {filename}")
        return file_path


# Convenience function
def get_migration_manager(migrations_dir: str = None) -> MigrationManager:
    """Get a MigrationManager instance"""
    return MigrationManager(migrations_dir)


__all__ = [
    'Migration',
    'MigrationManager', 
    'MigrationError',
    'get_migration_manager'
]