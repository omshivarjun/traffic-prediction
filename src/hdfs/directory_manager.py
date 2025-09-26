#!/usr/bin/env python3
"""
HDFS Directory Management Utilities - Task 10.2
==============================================
Comprehensive HDFS directory management with retention policies,
file naming conventions, and replication management.
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class HDFSDirectoryConfig:
    """Configuration for HDFS directory management"""
    hdfs_base_path: str = "hdfs://localhost:9000/traffic"
    retention_days: int = 30
    replication_factor: int = 3
    block_size: str = "128MB"
    backup_path: str = "hdfs://localhost:9000/traffic/backup"
    
    # Directory structure
    raw_data_path: str = "hdfs://localhost:9000/traffic/raw"
    processed_data_path: str = "hdfs://localhost:9000/traffic/processed"
    aggregated_data_path: str = "hdfs://localhost:9000/traffic/aggregated"
    streaming_data_path: str = "hdfs://localhost:9000/traffic/streaming"
    validation_data_path: str = "hdfs://localhost:9000/traffic/validated"
    
    # File naming patterns
    file_prefix: str = "traffic_data"
    timestamp_format: str = "%Y%m%d_%H%M%S"
    compression_suffix: str = ".parquet.snappy"


class HDFSDirectoryManager:
    """Comprehensive HDFS directory management system"""
    
    def __init__(self, config: HDFSDirectoryConfig):
        """Initialize HDFS directory manager"""
        self.config = config
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("hdfs_directory_manager")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        return logger
    
    def _run_hdfs_command(self, command: List[str], timeout: int = 60) -> Tuple[bool, str, str]:
        """Run HDFS command via Docker container"""
        try:
            # Prefix with Docker exec command
            full_command = ["docker", "exec", "namenode-alt"] + command
            
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return (result.returncode == 0, result.stdout, result.stderr)
            
        except subprocess.TimeoutExpired:
            return (False, "", "Command timed out")
        except Exception as e:
            return (False, "", str(e))
    
    def create_directory_structure(self) -> bool:
        """Create complete HDFS directory structure"""
        self.logger.info("Creating HDFS directory structure...")
        
        # Define directory hierarchy
        directories = {
            "base": self.config.hdfs_base_path,
            "raw": self.config.raw_data_path,
            "processed": self.config.processed_data_path,
            "aggregated": self.config.aggregated_data_path,
            "streaming": self.config.streaming_data_path,
            "validated": self.config.validation_data_path,
            "backup": self.config.backup_path,
            "temp": f"{self.config.hdfs_base_path}/temp",
            "reports": f"{self.config.hdfs_base_path}/reports",
            "checkpoints": f"{self.config.hdfs_base_path}/checkpoints"
        }
        
        # Add date-based subdirectories for current year
        current_year = datetime.now().year
        for month in range(1, 13):
            month_str = f"{month:02d}"
            for base_type in ["raw", "processed", "aggregated", "streaming"]:
                yearly_path = f"{directories[base_type]}/year={current_year}/month={month_str}"
                directories[f"{base_type}_y{current_year}_m{month}"] = yearly_path
        
        success_count = 0
        total_count = len(directories)
        
        for dir_name, dir_path in directories.items():
            success, stdout, stderr = self._run_hdfs_command([
                "hdfs", "dfs", "-mkdir", "-p", dir_path
            ])
            
            if success:
                self.logger.info(f"✅ Created directory: {dir_name} -> {dir_path}")
                success_count += 1
                
                # Set replication factor
                self._run_hdfs_command([
                    "hdfs", "dfs", "-setrep", str(self.config.replication_factor), dir_path
                ])
                
            else:
                if "File exists" in stderr:
                    self.logger.info(f"✅ Directory exists: {dir_name} -> {dir_path}")
                    success_count += 1
                else:
                    self.logger.error(f"❌ Failed to create: {dir_name} -> {stderr}")
        
        success_rate = success_count / total_count
        self.logger.info(f"Directory creation completed: {success_count}/{total_count} ({success_rate:.1%})")
        
        return success_rate >= 0.9  # Consider successful if 90% of directories created
    
    def set_directory_permissions(self) -> bool:
        """Set appropriate permissions for HDFS directories"""
        self.logger.info("Setting HDFS directory permissions...")
        
        permission_settings = [
            (self.config.hdfs_base_path, "755"),
            (self.config.raw_data_path, "755"),
            (self.config.processed_data_path, "755"),
            (self.config.aggregated_data_path, "755"),
            (self.config.streaming_data_path, "755"),
            (self.config.validation_data_path, "755"),
            (self.config.backup_path, "700"),  # More restrictive for backups
            (f"{self.config.hdfs_base_path}/temp", "777")  # Temporary directory
        ]
        
        success_count = 0
        
        for path, permission in permission_settings:
            success, stdout, stderr = self._run_hdfs_command([
                "hdfs", "dfs", "-chmod", permission, path
            ])
            
            if success:
                self.logger.info(f"✅ Set permissions {permission} for: {path}")
                success_count += 1
            else:
                self.logger.error(f"❌ Failed to set permissions for {path}: {stderr}")
        
        return success_count == len(permission_settings)
    
    def generate_file_name(self, data_type: str, timestamp: Optional[datetime] = None, 
                          segment_id: Optional[str] = None) -> str:
        """Generate standardized file names"""
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_str = timestamp.strftime(self.config.timestamp_format)
        
        # Base filename
        filename = f"{self.config.file_prefix}_{data_type}_{timestamp_str}"
        
        # Add segment if specified
        if segment_id:
            filename += f"_seg_{segment_id}"
        
        # Add compression suffix
        filename += self.config.compression_suffix
        
        return filename
    
    def get_partition_path(self, base_path: str, timestamp: datetime) -> str:
        """Generate partition path based on timestamp"""
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day
        hour = timestamp.hour
        
        partition_path = f"{base_path}/year={year}/month={month:02d}/day={day:02d}/hour={hour:02d}"
        return partition_path
    
    def list_directory_contents(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """List contents of HDFS directory"""
        self.logger.info(f"Listing contents of: {path}")
        
        command = ["hdfs", "dfs", "-ls"]
        if recursive:
            command.append("-R")
        command.append(path)
        
        success, stdout, stderr = self._run_hdfs_command(command)
        
        if not success:
            return {"success": False, "error": stderr, "files": []}
        
        files = []
        directories = []
        total_size = 0
        
        for line in stdout.strip().split('\n'):
            if line.startswith('Found') or not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= 8:
                permissions = parts[0]
                replication = parts[1]
                user = parts[2]
                group = parts[3]
                size = int(parts[4]) if parts[4].isdigit() else 0
                date = parts[5]
                time = parts[6]
                file_path = parts[7]
                
                file_info = {
                    "path": file_path,
                    "permissions": permissions,
                    "size": size,
                    "date": date,
                    "time": time,
                    "user": user,
                    "group": group,
                    "is_directory": permissions.startswith('d')
                }
                
                if file_info["is_directory"]:
                    directories.append(file_info)
                else:
                    files.append(file_info)
                    total_size += size
        
        return {
            "success": True,
            "path": path,
            "files": files,
            "directories": directories,
            "file_count": len(files),
            "directory_count": len(directories),
            "total_size": total_size,
            "total_size_mb": total_size / (1024 * 1024)
        }
    
    def cleanup_old_files(self, base_path: str, retention_days: Optional[int] = None) -> Dict[str, Any]:
        """Clean up files older than retention period"""
        if retention_days is None:
            retention_days = self.config.retention_days
        
        self.logger.info(f"Cleaning up files older than {retention_days} days from: {base_path}")
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_date.timestamp()
        
        cleanup_results = {
            "cutoff_date": cutoff_date.isoformat(),
            "files_deleted": [],
            "directories_deleted": [],
            "total_space_freed": 0,
            "errors": []
        }
        
        try:
            # List all files recursively
            directory_info = self.list_directory_contents(base_path, recursive=True)
            
            if not directory_info["success"]:
                cleanup_results["errors"].append(f"Failed to list directory: {directory_info['error']}")
                return cleanup_results
            
            # Identify files to delete based on date patterns in path
            for file_info in directory_info["files"]:
                file_path = file_info["path"]
                
                # Extract date from partition path (year=YYYY/month=MM/day=DD)
                if "/year=" in file_path and "/month=" in file_path and "/day=" in file_path:
                    try:
                        # Extract year, month, day from path
                        path_parts = file_path.split('/')
                        year_part = [p for p in path_parts if p.startswith('year=')]
                        month_part = [p for p in path_parts if p.startswith('month=')]
                        day_part = [p for p in path_parts if p.startswith('day=')]
                        
                        if year_part and month_part and day_part:
                            year = int(year_part[0].split('=')[1])
                            month = int(month_part[0].split('=')[1])
                            day = int(day_part[0].split('=')[1])
                            
                            file_date = datetime(year, month, day)
                            
                            if file_date < cutoff_date:
                                # Delete the file
                                success, stdout, stderr = self._run_hdfs_command([
                                    "hdfs", "dfs", "-rm", file_path
                                ])
                                
                                if success:
                                    cleanup_results["files_deleted"].append({
                                        "path": file_path,
                                        "size": file_info["size"],
                                        "date": file_date.isoformat()
                                    })
                                    cleanup_results["total_space_freed"] += file_info["size"]
                                    self.logger.info(f"Deleted old file: {file_path}")
                                else:
                                    cleanup_results["errors"].append(f"Failed to delete {file_path}: {stderr}")
                    
                    except (ValueError, IndexError) as e:
                        cleanup_results["errors"].append(f"Failed to parse date from path {file_path}: {e}")
            
            # Clean up empty directories
            self._cleanup_empty_directories(base_path, cleanup_results)
            
            self.logger.info(f"Cleanup completed: {len(cleanup_results['files_deleted'])} files deleted, "
                           f"{cleanup_results['total_space_freed'] / (1024*1024):.2f} MB freed")
            
        except Exception as e:
            cleanup_results["errors"].append(f"Cleanup failed: {e}")
        
        return cleanup_results
    
    def _cleanup_empty_directories(self, base_path: str, cleanup_results: Dict):
        """Remove empty directories after file cleanup"""
        # List directories and check if they're empty
        directory_info = self.list_directory_contents(base_path, recursive=True)
        
        if directory_info["success"]:
            # Sort directories by depth (deepest first) for proper cleanup
            directories = sorted(directory_info["directories"], 
                               key=lambda x: x["path"].count('/'), reverse=True)
            
            for dir_info in directories:
                dir_path = dir_info["path"]
                
                # Skip base directories
                if dir_path in [base_path, self.config.hdfs_base_path]:
                    continue
                
                # Check if directory is empty
                dir_contents = self.list_directory_contents(dir_path)
                if (dir_contents["success"] and 
                    dir_contents["file_count"] == 0 and 
                    dir_contents["directory_count"] == 0):
                    
                    success, stdout, stderr = self._run_hdfs_command([
                        "hdfs", "dfs", "-rmdir", dir_path
                    ])
                    
                    if success:
                        cleanup_results["directories_deleted"].append(dir_path)
                        self.logger.info(f"Removed empty directory: {dir_path}")
    
    def backup_directory(self, source_path: str, backup_name: Optional[str] = None) -> bool:
        """Create backup of directory"""
        if backup_name is None:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = f"{self.config.backup_path}/{backup_name}"
        
        self.logger.info(f"Creating backup: {source_path} -> {backup_path}")
        
        success, stdout, stderr = self._run_hdfs_command([
            "hdfs", "dfs", "-cp", "-r", source_path, backup_path
        ])
        
        if success:
            self.logger.info(f"✅ Backup created: {backup_path}")
            return True
        else:
            self.logger.error(f"❌ Backup failed: {stderr}")
            return False
    
    def get_directory_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all managed directories"""
        self.logger.info("Gathering directory statistics...")
        
        directories_to_check = [
            ("base", self.config.hdfs_base_path),
            ("raw", self.config.raw_data_path),
            ("processed", self.config.processed_data_path),
            ("aggregated", self.config.aggregated_data_path),
            ("streaming", self.config.streaming_data_path),
            ("validated", self.config.validation_data_path),
            ("backup", self.config.backup_path)
        ]
        
        stats = {
            "report_timestamp": datetime.now().isoformat(),
            "directories": {},
            "total_files": 0,
            "total_size_mb": 0,
            "oldest_file": None,
            "newest_file": None
        }
        
        for dir_name, dir_path in directories_to_check:
            dir_info = self.list_directory_contents(dir_path, recursive=True)
            
            if dir_info["success"]:
                stats["directories"][dir_name] = {
                    "path": dir_path,
                    "file_count": dir_info["file_count"],
                    "directory_count": dir_info["directory_count"],
                    "total_size_mb": dir_info["total_size_mb"],
                    "exists": True
                }
                
                stats["total_files"] += dir_info["file_count"]
                stats["total_size_mb"] += dir_info["total_size_mb"]
            else:
                stats["directories"][dir_name] = {
                    "path": dir_path,
                    "exists": False,
                    "error": dir_info.get("error", "Unknown error")
                }
        
        return stats
    
    def validate_directory_health(self) -> Dict[str, Any]:
        """Validate health of HDFS directory structure"""
        self.logger.info("Validating HDFS directory health...")
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": "HEALTHY",
            "issues": [],
            "recommendations": [],
            "directory_checks": {}
        }
        
        # Check each main directory
        main_directories = [
            self.config.hdfs_base_path,
            self.config.raw_data_path,
            self.config.processed_data_path,
            self.config.aggregated_data_path,
            self.config.streaming_data_path
        ]
        
        for directory in main_directories:
            dir_info = self.list_directory_contents(directory)
            dir_name = directory.split('/')[-1]
            
            health_report["directory_checks"][dir_name] = {
                "path": directory,
                "accessible": dir_info["success"],
                "file_count": dir_info.get("file_count", 0),
                "total_size_mb": dir_info.get("total_size_mb", 0)
            }
            
            if not dir_info["success"]:
                health_report["issues"].append(f"Directory not accessible: {directory}")
                health_report["overall_health"] = "DEGRADED"
        
        # Check for potential issues
        stats = self.get_directory_stats()
        
        # Large number of small files
        if stats["total_files"] > 100000:
            health_report["issues"].append("Large number of files detected - consider compaction")
            health_report["recommendations"].append("Run file compaction job")
        
        # Very large total size
        if stats["total_size_mb"] > 100000:  # 100GB
            health_report["recommendations"].append("Consider implementing data archival strategy")
        
        # Set overall health based on issues
        if len(health_report["issues"]) > 3:
            health_report["overall_health"] = "UNHEALTHY"
        elif len(health_report["issues"]) > 0:
            health_report["overall_health"] = "DEGRADED"
        
        return health_report


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HDFS Directory Management')
    parser.add_argument('--action', '-a', 
                       choices=['create', 'cleanup', 'backup', 'stats', 'health'],
                       default='create',
                       help='Action to perform')
    parser.add_argument('--retention-days', '-r', type=int, default=30,
                       help='Retention period in days')
    parser.add_argument('--backup-name', '-b', 
                       help='Backup name (for backup action)')
    parser.add_argument('--config', '-c', default='config/hdfs_storage_config.json',
                       help='Configuration file path')
    
    args = parser.parse_args()
    
    # Load configuration if available
    config = HDFSDirectoryConfig()
    config_path = Path(args.config)
    if config_path.exists():
        try:
            with open(config_path) as f:
                config_data = json.load(f)
            # Update config with loaded values
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
    
    manager = HDFSDirectoryManager(config)
    
    try:
        if args.action == 'create':
            print("Creating HDFS directory structure...")
            success = manager.create_directory_structure()
            if success:
                manager.set_directory_permissions()
                print("✅ Directory structure created successfully")
            else:
                print("❌ Failed to create directory structure")
                return 1
        
        elif args.action == 'cleanup':
            print(f"Cleaning up old files (retention: {args.retention_days} days)...")
            results = manager.cleanup_old_files(config.hdfs_base_path, args.retention_days)
            print(f"✅ Cleanup completed: {len(results['files_deleted'])} files deleted")
            print(f"   Space freed: {results['total_space_freed'] / (1024*1024):.2f} MB")
        
        elif args.action == 'backup':
            print("Creating backup...")
            success = manager.backup_directory(config.hdfs_base_path, args.backup_name)
            if success:
                print("✅ Backup created successfully")
            else:
                print("❌ Backup failed")
                return 1
        
        elif args.action == 'stats':
            print("Gathering directory statistics...")
            stats = manager.get_directory_stats()
            print(f"Total files: {stats['total_files']:,}")
            print(f"Total size: {stats['total_size_mb']:.2f} MB")
            
            # Save detailed stats
            stats_file = f"logs/hdfs_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            os.makedirs("logs", exist_ok=True)
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
            print(f"Detailed stats saved to: {stats_file}")
        
        elif args.action == 'health':
            print("Validating directory health...")
            health = manager.validate_directory_health()
            print(f"Overall health: {health['overall_health']}")
            if health['issues']:
                print("Issues found:")
                for issue in health['issues']:
                    print(f"  - {issue}")
            
            # Save health report
            health_file = f"logs/hdfs_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            os.makedirs("logs", exist_ok=True)
            with open(health_file, 'w') as f:
                json.dump(health, f, indent=2)
            print(f"Health report saved to: {health_file}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Operation failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())