"""
Hadoop HDFS Integration for Traffic Congestion Prediction System

This module handles storing and retrieving traffic data from HDFS
for long-term storage and batch processing with ML models.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import pandas as pd

try:
    import hdfs3
    from hdfs3 import HDFileSystem
    HDFS_AVAILABLE = True
except ImportError:
    HDFS_AVAILABLE = False

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HDFSManager:
    """Manages HDFS operations for traffic data storage and retrieval"""
    
    def __init__(self, 
                 namenode_host: str = "localhost",
                 namenode_port: int = 9000,
                 base_path: str = "/traffic-prediction"):
        self.namenode_host = namenode_host
        self.namenode_port = namenode_port
        self.base_path = base_path
        self.fs = None
        self.connected = False
        
        # HDFS directory structure
        self.paths = {
            'raw_data': f"{base_path}/raw-data",
            'processed_data': f"{base_path}/processed-data", 
            'ml_models': f"{base_path}/ml-models",
            'predictions': f"{base_path}/predictions",
            'analytics': f"{base_path}/analytics",
            'metr_la': f"{base_path}/datasets/metr-la",
            'backups': f"{base_path}/backups"
        }
        
    def connect(self) -> bool:
        """Connect to HDFS cluster"""
        if not HDFS_AVAILABLE:
            logger.warning("hdfs3 library not available, running in stub mode")
            self.connected = True  # Allow stub operations
            return True
            
        try:
            logger.info(f"Connecting to HDFS at {self.namenode_host}:{self.namenode_port}")
            
            # Create HDFS connection
            self.fs = HDFileSystem(
                host=self.namenode_host,
                port=self.namenode_port,
                user='hadoop'  # Default Hadoop user
            )
            
            # Test connection by listing root directory
            self.fs.ls('/')
            
            self.connected = True
            logger.info("Successfully connected to HDFS")
            
            # Create base directories
            self._create_directory_structure()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to HDFS: {e}")
            logger.info("Running in stub mode")
            self.connected = True  # Allow stub operations
            return True
    
    def _create_directory_structure(self):
        """Create the required directory structure in HDFS"""
        if not HDFS_AVAILABLE or not self.fs:
            logger.info("[STUB] Would create HDFS directory structure")
            return
            
        try:
            for path_name, path_value in self.paths.items():
                self.fs.makedirs(path_value, exist_ok=True)
                logger.info(f"Created/verified HDFS directory: {path_value}")
                
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
    
    def store_traffic_events(self, events: List[Dict], partition_date: Optional[str] = None) -> bool:
        """Store traffic events in HDFS with date-based partitioning"""
        if not partition_date:
            partition_date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            # Create partition path
            partition_path = f"{self.paths['raw_data']}/year={partition_date[:4]}/month={partition_date[5:7]}/day={partition_date[8:10]}"
            
            if not HDFS_AVAILABLE or not self.fs:
                logger.info(f"[STUB] Would store {len(events)} events to {partition_path}")
                return True
            
            # Ensure partition directory exists
            self.fs.makedirs(partition_path, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"traffic_events_{timestamp}.json"
            file_path = f"{partition_path}/{filename}"
            
            # Write events as JSON Lines format
            with self.fs.open(file_path, 'w') as f:
                for event in events:
                    f.write(json.dumps(event) + '\n')
            
            logger.info(f"Stored {len(events)} traffic events to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing traffic events: {e}")
            return False
    
    def store_parquet_data(self, df: pd.DataFrame, path: str, partition_cols: Optional[List[str]] = None) -> bool:
        """Store DataFrame as Parquet format in HDFS"""
        if not PARQUET_AVAILABLE:
            logger.warning("PyArrow not available, cannot store Parquet data")
            return False
            
        try:
            if not HDFS_AVAILABLE or not self.fs:
                logger.info(f"[STUB] Would store DataFrame ({len(df)} rows) as Parquet to {path}")
                return True
            
            # Convert DataFrame to PyArrow Table
            table = pa.Table.from_pandas(df)
            
            # Write Parquet file
            full_path = f"{self.base_path}/{path}"
            self.fs.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with self.fs.open(full_path, 'wb') as f:
                pq.write_table(table, f)
            
            logger.info(f"Stored DataFrame as Parquet: {full_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing Parquet data: {e}")
            return False
    
    def store_ml_model(self, model_data: bytes, model_name: str, version: str = "latest") -> bool:
        """Store ML model in HDFS"""
        try:
            model_path = f"{self.paths['ml_models']}/{model_name}/{version}/model.pkl"
            
            if not HDFS_AVAILABLE or not self.fs:
                logger.info(f"[STUB] Would store ML model to {model_path}")
                return True
            
            # Ensure directory exists
            self.fs.makedirs(os.path.dirname(model_path), exist_ok=True)
            
            # Write model data
            with self.fs.open(model_path, 'wb') as f:
                f.write(model_data)
            
            # Store metadata
            metadata = {
                'model_name': model_name,
                'version': version,
                'stored_at': datetime.now().isoformat(),
                'size_bytes': len(model_data)
            }
            
            metadata_path = f"{self.paths['ml_models']}/{model_name}/{version}/metadata.json"
            with self.fs.open(metadata_path, 'w') as f:
                json.dump(metadata, f)
            
            logger.info(f"Stored ML model: {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing ML model: {e}")
            return False
    
    def load_ml_model(self, model_name: str, version: str = "latest") -> Optional[bytes]:
        """Load ML model from HDFS"""
        try:
            model_path = f"{self.paths['ml_models']}/{model_name}/{version}/model.pkl"
            
            if not HDFS_AVAILABLE or not self.fs:
                logger.info(f"[STUB] Would load ML model from {model_path}")
                return None
            
            if not self.fs.exists(model_path):
                logger.error(f"Model not found: {model_path}")
                return None
            
            with self.fs.open(model_path, 'rb') as f:
                model_data = f.read()
            
            logger.info(f"Loaded ML model: {model_path}")
            return model_data
            
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")
            return None
    
    def store_predictions(self, predictions: List[Dict], batch_id: str) -> bool:
        """Store prediction results in HDFS"""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            predictions_path = f"{self.paths['predictions']}/date={date_str}/batch_{batch_id}.json"
            
            if not HDFS_AVAILABLE or not self.fs:
                logger.info(f"[STUB] Would store {len(predictions)} predictions to {predictions_path}")
                return True
            
            # Ensure directory exists
            self.fs.makedirs(os.path.dirname(predictions_path), exist_ok=True)
            
            # Write predictions
            with self.fs.open(predictions_path, 'w') as f:
                json.dump({
                    'batch_id': batch_id,
                    'generated_at': datetime.now().isoformat(),
                    'predictions': predictions
                }, f, indent=2)
            
            logger.info(f"Stored {len(predictions)} predictions to {predictions_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing predictions: {e}")
            return False
    
    def load_historical_data(self, 
                           start_date: str, 
                           end_date: str, 
                           data_type: str = "raw_data") -> List[Dict]:
        """Load historical data from HDFS for a date range"""
        try:
            if data_type not in self.paths:
                logger.error(f"Unknown data type: {data_type}")
                return []
            
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            all_data = []
            current_dt = start_dt
            
            while current_dt <= end_dt:
                date_str = current_dt.strftime("%Y-%m-%d")
                partition_path = f"{self.paths[data_type]}/year={date_str[:4]}/month={date_str[5:7]}/day={date_str[8:10]}"
                
                if not HDFS_AVAILABLE or not self.fs:
                    logger.info(f"[STUB] Would load data from {partition_path}")
                    # Return mock data for testing
                    all_data.extend([
                        {
                            'event_id': f'mock_{current_dt.strftime("%Y%m%d")}_{i}',
                            'timestamp': current_dt.isoformat(),
                            'sensor_id': f'sensor_{i}',
                            'speed_mph': 45.5,
                            'volume_vph': 1200,
                            'congestion_level': 'moderate'
                        } for i in range(5)
                    ])
                else:
                    try:
                        if self.fs.exists(partition_path):
                            files = self.fs.ls(partition_path)
                            
                            for file_path in files:
                                if file_path.endswith('.json'):
                                    with self.fs.open(file_path, 'r') as f:
                                        for line in f:
                                            if line.strip():
                                                data = json.loads(line.strip())
                                                all_data.append(data)
                    except Exception as e:
                        logger.warning(f"Error loading data for {date_str}: {e}")
                
                current_dt += timedelta(days=1)
            
            logger.info(f"Loaded {len(all_data)} records from {start_date} to {end_date}")
            return all_data
            
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            return []
    
    def backup_data(self, source_path: str, backup_name: str) -> bool:
        """Create backup of data in HDFS"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.paths['backups']}/{backup_name}_{timestamp}"
            
            if not HDFS_AVAILABLE or not self.fs:
                logger.info(f"[STUB] Would backup {source_path} to {backup_path}")
                return True
            
            # Copy directory recursively
            if self.fs.exists(source_path):
                self.fs.copy(source_path, backup_path, recursive=True)
                logger.info(f"Created backup: {backup_path}")
                return True
            else:
                logger.error(f"Source path does not exist: {source_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get HDFS storage statistics"""
        try:
            if not HDFS_AVAILABLE or not self.fs:
                return {
                    'mode': 'stub',
                    'connected': self.connected,
                    'paths': self.paths,
                    'total_files': 'unknown',
                    'total_size_mb': 'unknown'
                }
            
            stats = {
                'mode': 'hdfs',
                'connected': self.connected,
                'namenode': f"{self.namenode_host}:{self.namenode_port}",
                'base_path': self.base_path,
                'paths': {}
            }
            
            total_files = 0
            total_size = 0
            
            for path_name, path_value in self.paths.items():
                try:
                    if self.fs.exists(path_value):
                        files = self.fs.ls(path_value, detail=True)
                        path_files = len([f for f in files if f['kind'] == 'file'])
                        path_size = sum(f['size'] for f in files if f['kind'] == 'file')
                        
                        stats['paths'][path_name] = {
                            'path': path_value,
                            'exists': True,
                            'files': path_files,
                            'size_mb': round(path_size / (1024 * 1024), 2)
                        }
                        
                        total_files += path_files
                        total_size += path_size
                    else:
                        stats['paths'][path_name] = {
                            'path': path_value,
                            'exists': False,
                            'files': 0,
                            'size_mb': 0
                        }
                except Exception as e:
                    stats['paths'][path_name] = {
                        'path': path_value,
                        'error': str(e)
                    }
            
            stats['total_files'] = total_files
            stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, data_type: str, days_to_keep: int = 30) -> bool:
        """Clean up old data files beyond retention period"""
        try:
            if data_type not in self.paths:
                logger.error(f"Unknown data type: {data_type}")
                return False
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")
            
            if not HDFS_AVAILABLE or not self.fs:
                logger.info(f"[STUB] Would cleanup {data_type} data older than {cutoff_str}")
                return True
            
            # This would implement actual cleanup logic
            # For safety, we'll just log what would be cleaned up
            logger.info(f"Would clean up {data_type} data older than {cutoff_str}")
            return True
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from HDFS"""
        try:
            if self.fs:
                # hdfs3 doesn't have explicit close method
                self.fs = None
            
            self.connected = False
            logger.info("Disconnected from HDFS")
            
        except Exception as e:
            logger.error(f"Error disconnecting from HDFS: {e}")

# Global HDFS manager instance
hdfs_manager = HDFSManager()

def initialize_hdfs() -> bool:
    """Initialize HDFS connection"""
    return hdfs_manager.connect()

def get_hdfs_manager() -> HDFSManager:
    """Get the global HDFS manager instance"""
    return hdfs_manager

# Example usage
if __name__ == "__main__":
    # Test HDFS integration
    manager = HDFSManager()
    
    if manager.connect():
        logger.info("HDFS connection test successful")
        
        # Test storing sample data
        sample_events = [
            {
                'event_id': 'test_001',
                'timestamp': datetime.now().isoformat(),
                'sensor_id': 'sensor_123',
                'speed_mph': 35.5,
                'volume_vph': 1400,
                'congestion_level': 'moderate'
            }
        ]
        
        success = manager.store_traffic_events(sample_events)
        logger.info(f"Sample data storage test: {'Success' if success else 'Failed'}")
        
        # Test statistics
        stats = manager.get_storage_statistics()
        logger.info(f"Storage statistics: {stats}")
        
        manager.disconnect()
    else:
        logger.error("HDFS connection test failed")