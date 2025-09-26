#!/usr/bin/env python3
"""
HDFS Storage Pipeline for METR-LA Traffic Data
Manages structured storage of real-time traffic data with time-based partitioning
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

logger = logging.getLogger("hdfs_pipeline")

@dataclass
class HDFSStorageConfig:
    """Configuration for HDFS storage pipeline"""
    # HDFS Configuration
    hdfs_host: str = "localhost"
    hdfs_port: int = 9000
    hdfs_base_path: str = "/traffic-data"
    
    # Storage Paths
    raw_data_path: str = "/traffic-data/raw/metr-la"
    processed_data_path: str = "/traffic-data/processed/metr-la"
    streaming_data_path: str = "/traffic-data/streaming/metr-la"
    models_path: str = "/traffic-data/models"
    predictions_path: str = "/traffic-data/predictions"
    
    # Partitioning Configuration
    partition_format: str = "year={year}/month={month:02d}/day={day:02d}/hour={hour:02d}"
    retention_days: int = 90  # Keep 3 months of data
    
    # File Formats
    raw_format: str = "parquet"
    processed_format: str = "parquet"
    streaming_format: str = "parquet"
    
    # Replication and Block Size
    replication_factor: int = 3
    block_size_mb: int = 128  # MB
    
    # Compression
    compression: str = "snappy"

class HDFSStorageManager:
    """Manager for HDFS storage operations"""
    
    def __init__(self, config: HDFSStorageConfig):
        """Initialize HDFS storage manager"""
        self.config = config
        self.hdfs_url = f"hdfs://{config.hdfs_host}:{config.hdfs_port}"
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("hdfs_pipeline")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def run_hdfs_command(self, command: List[str]) -> Tuple[bool, str, str]:
        """Run HDFS command and return success, stdout, stderr"""
        try:
            self.logger.debug(f"Running HDFS command: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            success = result.returncode == 0
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            self.logger.error("HDFS command timed out")
            return False, "", "Command timed out"
        except Exception as e:
            self.logger.error(f"Failed to run HDFS command: {e}")
            return False, "", str(e)
    
    def check_hdfs_connection(self) -> bool:
        """Check if HDFS is accessible"""
        self.logger.info("Checking HDFS connection...")
        
        success, stdout, stderr = self.run_hdfs_command(["hdfs", "dfsadmin", "-report"])
        
        if success:
            self.logger.info("✅ HDFS connection successful")
            # Extract basic cluster info
            lines = stdout.split('\n')
            for line in lines[:10]:  # First 10 lines usually contain cluster info
                if line.strip() and not line.startswith('Configured Capacity:'):
                    self.logger.info(f"  {line.strip()}")
            return True
        else:
            self.logger.error(f"❌ HDFS connection failed: {stderr}")
            return False
    
    def create_directory_structure(self) -> bool:
        """Create HDFS directory structure for traffic data"""
        self.logger.info("Creating HDFS directory structure...")
        
        directories = [
            self.config.hdfs_base_path,
            self.config.raw_data_path,
            self.config.processed_data_path,
            self.config.streaming_data_path,
            self.config.models_path,
            self.config.predictions_path
        ]
        
        all_success = True
        
        for directory in directories:
            self.logger.info(f"Creating directory: {directory}")
            
            success, stdout, stderr = self.run_hdfs_command([
                "hdfs", "dfs", "-mkdir", "-p", directory
            ])
            
            if success:
                self.logger.info(f"  ✅ Created: {directory}")
                
                # Set appropriate permissions
                self.run_hdfs_command([
                    "hdfs", "dfs", "-chmod", "755", directory
                ])
                
            else:
                if "File exists" in stderr:
                    self.logger.info(f"  ℹ️  Already exists: {directory}")
                else:
                    self.logger.error(f"  ❌ Failed to create {directory}: {stderr}")
                    all_success = False
        
        return all_success
    
    def set_storage_policies(self) -> bool:
        """Set storage policies for different data types"""
        self.logger.info("Setting HDFS storage policies...")
        
        policies = [
            (self.config.raw_data_path, "HOT"),  # Frequently accessed
            (self.config.processed_data_path, "WARM"),  # Less frequent access
            (self.config.streaming_data_path, "HOT"),  # Real-time access
            (self.config.models_path, "COLD"),  # Archive storage
            (self.config.predictions_path, "HOT")  # Frequent access
        ]
        
        all_success = True
        
        for path, policy in policies:
            self.logger.info(f"Setting {policy} policy for: {path}")
            
            success, stdout, stderr = self.run_hdfs_command([
                "hdfs", "storagepolicies", "-setStoragePolicy", 
                "-path", path, "-policy", policy
            ])
            
            if success:
                self.logger.info(f"  ✅ Set {policy} policy for {path}")
            else:
                self.logger.warning(f"  ⚠️  Failed to set policy for {path}: {stderr}")
                # Don't fail completely for storage policy issues
        
        return all_success
    
    def get_directory_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get information about HDFS directory"""
        success, stdout, stderr = self.run_hdfs_command([
            "hdfs", "dfs", "-du", "-s", "-h", path
        ])
        
        if not success:
            return None
        
        # Parse output
        lines = stdout.strip().split('\n')
        if lines and lines[0]:
            parts = lines[0].split()
            if len(parts) >= 3:
                return {
                    "size": parts[0],
                    "size_disk": parts[1], 
                    "path": parts[2] if len(parts) > 2 else path
                }
        
        return {"size": "0", "size_disk": "0", "path": path}
    
    def list_partitions(self, base_path: str, depth: int = 4) -> List[str]:
        """List existing partitions in HDFS"""
        success, stdout, stderr = self.run_hdfs_command([
            "hdfs", "dfs", "-ls", "-R", base_path
        ])
        
        if not success:
            return []
        
        partitions = []
        lines = stdout.strip().split('\n')
        
        for line in lines:
            if line.startswith('drwx') and '=' in line:
                # Extract partition path
                parts = line.split()
                if len(parts) >= 8:
                    partition_path = parts[7]
                    partitions.append(partition_path)
        
        return sorted(partitions)
    
    def cleanup_old_partitions(self, base_path: str) -> bool:
        """Clean up old partitions based on retention policy"""
        self.logger.info(f"Cleaning up old partitions in: {base_path}")
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
        
        partitions = self.list_partitions(base_path)
        deleted_count = 0
        
        for partition in partitions:
            try:
                # Extract date from partition path
                # Assuming format: .../year=2024/month=01/day=15/hour=10
                path_parts = partition.split('/')
                year_part = next((p for p in path_parts if p.startswith('year=')), None)
                month_part = next((p for p in path_parts if p.startswith('month=')), None)
                day_part = next((p for p in path_parts if p.startswith('day=')), None)
                
                if year_part and month_part and day_part:
                    year = int(year_part.split('=')[1])
                    month = int(month_part.split('=')[1])
                    day = int(day_part.split('=')[1])
                    
                    partition_date = datetime(year, month, day)
                    
                    if partition_date < cutoff_date:
                        self.logger.info(f"Deleting old partition: {partition}")
                        
                        success, stdout, stderr = self.run_hdfs_command([
                            "hdfs", "dfs", "-rm", "-r", "-skipTrash", partition
                        ])
                        
                        if success:
                            deleted_count += 1
                            self.logger.info(f"  ✅ Deleted: {partition}")
                        else:
                            self.logger.error(f"  ❌ Failed to delete {partition}: {stderr}")
                
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Could not parse partition date from {partition}: {e}")
        
        self.logger.info(f"Cleaned up {deleted_count} old partitions")
        return True
    
    def generate_storage_report(self) -> Dict[str, Any]:
        """Generate storage usage report"""
        self.logger.info("Generating HDFS storage report...")
        
        paths = [
            ("Raw Data", self.config.raw_data_path),
            ("Processed Data", self.config.processed_data_path),
            ("Streaming Data", self.config.streaming_data_path),
            ("Models", self.config.models_path),
            ("Predictions", self.config.predictions_path)
        ]
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "hdfs_url": self.hdfs_url,
            "storage_usage": {},
            "partitions": {},
            "total_size": "0"
        }
        
        total_size_bytes = 0
        
        for name, path in paths:
            info = self.get_directory_info(path)
            if info:
                report["storage_usage"][name] = info
                
                # Get partition count
                partitions = self.list_partitions(path)
                report["partitions"][name] = len(partitions)
                
                # Try to convert size to bytes for total calculation
                try:
                    size_str = info["size"]
                    if size_str.endswith('K'):
                        total_size_bytes += float(size_str[:-1]) * 1024
                    elif size_str.endswith('M'):
                        total_size_bytes += float(size_str[:-1]) * 1024 * 1024
                    elif size_str.endswith('G'):
                        total_size_bytes += float(size_str[:-1]) * 1024 * 1024 * 1024
                    elif size_str.endswith('T'):
                        total_size_bytes += float(size_str[:-1]) * 1024 * 1024 * 1024 * 1024
                    else:
                        total_size_bytes += float(size_str) if size_str.isdigit() else 0
                except (ValueError, IndexError):
                    pass
        
        # Format total size
        if total_size_bytes > 1024 * 1024 * 1024:
            report["total_size"] = f"{total_size_bytes / (1024 * 1024 * 1024):.2f}G"
        elif total_size_bytes > 1024 * 1024:
            report["total_size"] = f"{total_size_bytes / (1024 * 1024):.2f}M"
        elif total_size_bytes > 1024:
            report["total_size"] = f"{total_size_bytes / 1024:.2f}K"
        else:
            report["total_size"] = f"{int(total_size_bytes)}"
        
        return report
    
    def initialize_storage(self) -> bool:
        """Initialize HDFS storage for METR-LA traffic data"""
        self.logger.info("🚀 Initializing HDFS storage for METR-LA traffic data")
        
        success = True
        
        # Check HDFS connection
        if not self.check_hdfs_connection():
            return False
        
        # Create directory structure
        if not self.create_directory_structure():
            success = False
        
        # Set storage policies (optional, don't fail if not supported)
        self.set_storage_policies()
        
        if success:
            self.logger.info("✅ HDFS storage initialization completed successfully")
        else:
            self.logger.error("❌ HDFS storage initialization failed")
        
        return success

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HDFS Storage Pipeline for METR-LA Traffic Data')
    parser.add_argument('--hdfs-host', default='localhost', help='HDFS host')
    parser.add_argument('--hdfs-port', type=int, default=9000, help='HDFS port')
    parser.add_argument('--base-path', default='/traffic-data', help='Base HDFS path')
    parser.add_argument('--retention-days', type=int, default=90, help='Data retention in days')
    parser.add_argument('--action', choices=['init', 'report', 'cleanup'], 
                       default='init', help='Action to perform')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create configuration
    config = HDFSStorageConfig(
        hdfs_host=args.hdfs_host,
        hdfs_port=args.hdfs_port,
        hdfs_base_path=args.base_path,
        retention_days=args.retention_days
    )
    
    # Initialize manager
    manager = HDFSStorageManager(config)
    
    try:
        if args.action == 'init':
            success = manager.initialize_storage()
            if success:
                print("✅ HDFS storage initialization completed!")
                
                # Generate initial report
                report = manager.generate_storage_report()
                print("\n📊 Storage Report:")
                print(f"   Total Size: {report['total_size']}")
                for name, info in report["storage_usage"].items():
                    partition_count = report["partitions"].get(name, 0)
                    print(f"   {name}: {info['size']} ({partition_count} partitions)")
                
                return 0
            else:
                print("❌ HDFS storage initialization failed!")
                return 1
                
        elif args.action == 'report':
            report = manager.generate_storage_report()
            
            print("\n📊 HDFS Storage Report")
            print("=" * 50)
            print(f"Timestamp: {report['timestamp']}")
            print(f"HDFS URL: {report['hdfs_url']}")
            print(f"Total Size: {report['total_size']}")
            print("\nStorage Usage by Category:")
            
            for name, info in report["storage_usage"].items():
                partition_count = report["partitions"].get(name, 0)
                print(f"  {name:15}: {info['size']:>8} ({partition_count:>3} partitions)")
                if args.verbose:
                    print(f"    Path: {info['path']}")
                    print(f"    Disk Usage: {info['size_disk']}")
            
            # Save report
            report_file = f"hdfs_storage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nReport saved to: {report_file}")
            
            return 0
            
        elif args.action == 'cleanup':
            print("🧹 Starting cleanup of old partitions...")
            
            paths = [
                config.raw_data_path,
                config.processed_data_path,
                config.streaming_data_path,
                config.predictions_path
            ]
            
            for path in paths:
                manager.cleanup_old_partitions(path)
            
            print("✅ Cleanup completed!")
            return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=args.verbose)
        return 1

if __name__ == "__main__":
    exit(main())