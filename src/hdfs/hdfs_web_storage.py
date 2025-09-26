#!/usr/bin/env python3
"""
HDFS Web API Storage Pipeline for METR-LA Traffic Data
Uses HDFS WebHDFS REST API for storage management when CLI tools are not available
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
import urllib.parse

logger = logging.getLogger("hdfs_web_pipeline")

@dataclass
class HDFSWebConfig:
    """Configuration for HDFS Web API storage pipeline"""
    # HDFS WebHDFS Configuration
    hdfs_host: str = "localhost"
    hdfs_port: int = 9870  # WebHDFS port
    webhdfs_version: str = "v1"
    
    # Storage Paths
    hdfs_base_path: str = "/traffic-data"
    raw_data_path: str = "/traffic-data/raw/metr-la"
    processed_data_path: str = "/traffic-data/processed/metr-la"
    streaming_data_path: str = "/traffic-data/streaming/metr-la"
    models_path: str = "/traffic-data/models"
    predictions_path: str = "/traffic-data/predictions"
    
    # API Configuration
    timeout_seconds: int = 30
    user: str = "hadoop"  # Default HDFS user

class HDFSWebManager:
    """Manager for HDFS operations using WebHDFS REST API"""
    
    def __init__(self, config: HDFSWebConfig):
        """Initialize HDFS web manager"""
        self.config = config
        self.base_url = f"http://{config.hdfs_host}:{config.hdfs_port}/webhdfs/{config.webhdfs_version}"
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("hdfs_web_pipeline")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _make_webhdfs_url(self, path: str, operation: str, **params) -> str:
        """Create WebHDFS URL for given path and operation"""
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
        
        # Build URL
        url = f"{self.base_url}{path}"
        
        # Add parameters
        params['op'] = operation
        params['user.name'] = self.config.user
        
        # URL encode parameters
        query_string = urllib.parse.urlencode(params)
        return f"{url}?{query_string}"
    
    def check_hdfs_connection(self) -> bool:
        """Check if HDFS WebHDFS is accessible"""
        self.logger.info("Checking HDFS WebHDFS connection...")
        
        try:
            url = self._make_webhdfs_url("/", "GETFILESTATUS")
            response = requests.get(url, timeout=self.config.timeout_seconds)
            
            if response.status_code == 200:
                self.logger.info("SUCCESS: HDFS WebHDFS connection successful")
                
                # Log basic cluster info
                data = response.json()
                if 'FileStatus' in data:
                    file_status = data['FileStatus']
                    self.logger.info(f"  Root directory: {file_status.get('pathSuffix', '/')}")
                    self.logger.info(f"  Owner: {file_status.get('owner', 'unknown')}")
                    self.logger.info(f"  Permissions: {file_status.get('permission', 'unknown')}")
                
                return True
            else:
                self.logger.error(f"❌ HDFS connection failed with status: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ HDFS connection failed: {e}")
            return False
    
    def create_directory(self, path: str) -> bool:
        """Create directory using WebHDFS"""
        try:
            url = self._make_webhdfs_url(path, "MKDIRS", permission="755")
            response = requests.put(url, timeout=self.config.timeout_seconds)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('boolean', False):
                    self.logger.info(f"  SUCCESS: Created: {path}")
                    return True
                else:
                    self.logger.info(f"  ℹ️  Already exists: {path}")
                    return True
            else:
                self.logger.error(f"  ❌ Failed to create {path}: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"  ❌ Failed to create {path}: {e}")
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
            if not self.create_directory(directory):
                all_success = False
        
        return all_success
    
    def get_directory_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get information about HDFS directory"""
        try:
            url = self._make_webhdfs_url(path, "GETCONTENTSUMMARY")
            response = requests.get(url, timeout=self.config.timeout_seconds)
            
            if response.status_code == 200:
                data = response.json()
                if 'ContentSummary' in data:
                    summary = data['ContentSummary']
                    
                    # Convert bytes to human readable format
                    length = summary.get('length', 0)
                    space_consumed = summary.get('spaceConsumed', 0)
                    
                    def format_bytes(bytes_val):
                        if bytes_val >= 1024 * 1024 * 1024:
                            return f"{bytes_val / (1024 * 1024 * 1024):.2f}G"
                        elif bytes_val >= 1024 * 1024:
                            return f"{bytes_val / (1024 * 1024):.2f}M"
                        elif bytes_val >= 1024:
                            return f"{bytes_val / 1024:.2f}K"
                        else:
                            return str(bytes_val)
                    
                    return {
                        "size": format_bytes(length),
                        "space_consumed": format_bytes(space_consumed),
                        "directory_count": summary.get('directoryCount', 0),
                        "file_count": summary.get('fileCount', 0),
                        "quota": summary.get('quota', -1),
                        "space_quota": summary.get('spaceQuota', -1),
                        "path": path
                    }
            
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get directory info for {path}: {e}")
            return None
    
    def list_directory(self, path: str) -> List[Dict[str, Any]]:
        """List contents of HDFS directory"""
        try:
            url = self._make_webhdfs_url(path, "LISTSTATUS")
            response = requests.get(url, timeout=self.config.timeout_seconds)
            
            if response.status_code == 200:
                data = response.json()
                if 'FileStatuses' in data and 'FileStatus' in data['FileStatuses']:
                    return data['FileStatuses']['FileStatus']
            
            return []
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to list directory {path}: {e}")
            return []
    
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
            "hdfs_url": f"http://{self.config.hdfs_host}:{self.config.hdfs_port}",
            "storage_usage": {},
            "total_files": 0,
            "total_directories": 0
        }
        
        total_files = 0
        total_directories = 0
        
        for name, path in paths:
            info = self.get_directory_info(path)
            if info:
                report["storage_usage"][name] = info
                total_files += info.get("file_count", 0)
                total_directories += info.get("directory_count", 0)
            else:
                report["storage_usage"][name] = {
                    "size": "0",
                    "space_consumed": "0",
                    "directory_count": 0,
                    "file_count": 0,
                    "path": path,
                    "status": "not_found"
                }
        
        report["total_files"] = total_files
        report["total_directories"] = total_directories
        
        return report
    
    def check_existing_data(self) -> Dict[str, Any]:
        """Check for existing data in HDFS"""
        self.logger.info("Checking for existing data in HDFS...")
        
        existing_data = {}
        
        paths_to_check = [
            ("traffic-data", "/traffic-data"),
            ("user-data", "/user"),
            ("tmp", "/tmp")
        ]
        
        for name, path in paths_to_check:
            contents = self.list_directory(path)
            if contents:
                existing_data[name] = {
                    "path": path,
                    "item_count": len(contents),
                    "items": [
                        {
                            "name": item.get("pathSuffix", ""),
                            "type": item.get("type", ""),
                            "size": item.get("length", 0),
                            "modification_time": item.get("modificationTime", 0)
                        }
                        for item in contents[:10]  # Limit to first 10 items
                    ]
                }
                
                self.logger.info(f"Found {len(contents)} items in {path}")
                if len(contents) > 10:
                    self.logger.info(f"  (showing first 10 items)")
                
                for item in contents[:5]:  # Show first 5 items
                    item_type = item.get("type", "UNKNOWN")
                    item_name = item.get("pathSuffix", "")
                    item_size = item.get("length", 0)
                    self.logger.info(f"    {item_type}: {item_name} ({item_size} bytes)")
        
        return existing_data
    
    def initialize_storage(self) -> bool:
        """Initialize HDFS storage for METR-LA traffic data"""
        self.logger.info("INITIALIZING HDFS storage for METR-LA traffic data")
        
        success = True
        
        # Check HDFS connection
        if not self.check_hdfs_connection():
            return False
        
        # Check existing data
        existing_data = self.check_existing_data()
        
        # Create directory structure
        if not self.create_directory_structure():
            success = False
        
        if success:
            self.logger.info("SUCCESS: HDFS storage initialization completed successfully")
        else:
            self.logger.error("❌ HDFS storage initialization failed")
        
        return success

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HDFS Web API Storage Pipeline for METR-LA Traffic Data')
    parser.add_argument('--hdfs-host', default='localhost', help='HDFS host')
    parser.add_argument('--hdfs-port', type=int, default=9870, help='HDFS WebHDFS port')
    parser.add_argument('--base-path', default='/traffic-data', help='Base HDFS path')
    parser.add_argument('--action', choices=['init', 'report', 'check'], 
                       default='init', help='Action to perform')
    parser.add_argument('--user', default='hadoop', help='HDFS user')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create configuration
    config = HDFSWebConfig(
        hdfs_host=args.hdfs_host,
        hdfs_port=args.hdfs_port,
        hdfs_base_path=args.base_path,
        user=args.user
    )
    
    # Initialize manager
    manager = HDFSWebManager(config)
    
    try:
        if args.action == 'init':
            success = manager.initialize_storage()
            if success:
                print("SUCCESS: HDFS storage initialization completed!")
                
                # Generate initial report
                report = manager.generate_storage_report()
                print("\nSTORAGE REPORT:")
                print(f"   Total Files: {report['total_files']}")
                print(f"   Total Directories: {report['total_directories']}")
                for name, info in report["storage_usage"].items():
                    print(f"   {name}: {info['size']} ({info['file_count']} files, {info['directory_count']} dirs)")
                
                return 0
            else:
                print("❌ HDFS storage initialization failed!")
                return 1
                
        elif args.action == 'report':
            report = manager.generate_storage_report()
            
            print("\nHDFS STORAGE REPORT")
            print("=" * 50)
            print(f"Timestamp: {report['timestamp']}")
            print(f"HDFS URL: {report['hdfs_url']}")
            print(f"Total Files: {report['total_files']}")
            print(f"Total Directories: {report['total_directories']}")
            print("\nStorage Usage by Category:")
            
            for name, info in report["storage_usage"].items():
                status = info.get("status", "ok")
                if status == "not_found":
                    print(f"  {name:15}: Not found")
                else:
                    print(f"  {name:15}: {info['size']:>8} ({info['file_count']:>3} files, {info['directory_count']:>3} dirs)")
                    if args.verbose:
                        print(f"    Path: {info['path']}")
                        print(f"    Space Consumed: {info['space_consumed']}")
            
            # Save report
            report_file = f"hdfs_storage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nReport saved to: {report_file}")
            
            return 0
            
        elif args.action == 'check':
            print("🔍 Checking existing HDFS data...")
            existing_data = manager.check_existing_data()
            
            if not existing_data:
                print("No existing data found in HDFS")
            else:
                print(f"Found data in {len(existing_data)} directories:")
                for name, info in existing_data.items():
                    print(f"\n{name} ({info['path']}):")
                    print(f"  Items: {info['item_count']}")
                    for item in info['items']:
                        print(f"    {item['type']}: {item['name']} ({item['size']} bytes)")
            
            return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=args.verbose)
        return 1

if __name__ == "__main__":
    exit(main())