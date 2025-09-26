#!/usr/bin/env python3
"""
Task 6.4: HDFS Data Upload System
Traffic Prediction System - Upload processed METR-LA dataset to HDFS

This script uploads the processed METR-LA traffic dataset to HDFS:
- Create required directory structure in HDFS
- Upload processed datasets to /user/traffic/raw/
- Set appropriate permissions for data access
- Verify upload success and data integrity
- Generate upload metadata and verification reports

The system integrates with the existing Hadoop infrastructure and
prepares data for downstream batch processing and ML training.
"""

import os
import sys
import subprocess
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
# import pandas as pd  # Not needed for this script

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HDFSUploader:
    """HDFS uploader for METR-LA traffic dataset"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.processed_dir = self.data_dir / "processed"
        
        # HDFS configuration
        self.hdfs_base_path = "/user/traffic"
        self.hdfs_raw_path = f"{self.hdfs_base_path}/raw"
        self.hdfs_processed_path = f"{self.hdfs_base_path}/processed"
        
        # Files to upload
        self.upload_files = {
            'sensor_metadata': self.data_dir / "raw" / "metr_la_sensor_metadata.csv",
            'raw_traffic_data': self.data_dir / "raw" / "metr_la_sample_data.csv",
            'processed_data': self.processed_dir / "metr_la_processed_data.csv",
            'essential_features': self.processed_dir / "metr_la_essential_features.csv",
            'ml_ready': self.processed_dir / "metr_la_ml_ready.csv",
            'preprocessing_metadata': self.processed_dir / "preprocessing_metadata.json"
        }
        
        # Check if alternative traffic data files exist
        full_traffic_file = self.data_dir / "raw" / "metr_la_traffic_data.csv"
        if full_traffic_file.exists():
            self.upload_files['raw_traffic_data'] = full_traffic_file
    
    def check_hadoop_status(self) -> bool:
        """Check if Hadoop services are running via Docker"""
        logger.info("Checking Hadoop service status...")
        
        try:
            # Check if namenode container is running
            result = subprocess.run(['docker', 'ps', '--filter', 'name=namenode-alt', '--format', '{{.Names}}'], 
                                  capture_output=True, text=True, timeout=10)
            if 'namenode-alt' not in result.stdout:
                logger.error("Hadoop namenode container not found")
                return False
                
            logger.info("✅ Hadoop namenode container is running")
            
            # Test HDFS connection via Docker
            test_result = subprocess.run(['docker', 'exec', 'namenode-alt', 'hdfs', 'dfs', '-ls', '/'], 
                                       capture_output=True, text=True, timeout=30)
            if test_result.returncode == 0:
                logger.info("✅ HDFS is accessible")
                return True
            else:
                logger.error(f"HDFS not accessible: {test_result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Docker/Hadoop command timed out - services may not be responding")
            return False
        except FileNotFoundError:
            logger.error("Docker command not found - check Docker installation")
            return False
        except Exception as e:
            logger.error(f"Error checking Hadoop status: {e}")
            return False
    
    def create_hdfs_directories(self) -> bool:
        """Create required directory structure in HDFS"""
        logger.info("Creating HDFS directory structure...")
        
        directories = [
            self.hdfs_base_path,
            self.hdfs_raw_path,
            self.hdfs_processed_path,
            f"{self.hdfs_raw_path}/metr_la",
            f"{self.hdfs_processed_path}/metr_la"
        ]
        
        try:
            for directory in directories:
                logger.info(f"Creating directory: {directory}")
                
                # Create directory with -p flag (create parents) via Docker
                result = subprocess.run(
                    ["docker", "exec", "namenode-alt", "hdfs", "dfs", "-mkdir", "-p", directory],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0 and "File exists" not in result.stderr:
                    logger.warning(f"Directory creation issue for {directory}: {result.stderr}")
                else:
                    logger.info(f"✅ Directory ready: {directory}")
            
            # Set permissions for traffic directories
            logger.info("Setting directory permissions...")
            
            for base_dir in [self.hdfs_base_path, self.hdfs_raw_path, self.hdfs_processed_path]:
                subprocess.run(
                    ["docker", "exec", "namenode-alt", "hdfs", "dfs", "-chmod", "755", base_dir],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            
            logger.info("✅ HDFS directory structure created")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create HDFS directories: {e}")
            return False
    
    def upload_file_to_hdfs(self, local_file: Path, hdfs_path: str, overwrite: bool = True) -> bool:
        """Upload a single file to HDFS"""
        if not local_file.exists():
            logger.error(f"Local file not found: {local_file}")
            return False
        
        logger.info(f"Uploading {local_file.name} to {hdfs_path}")
        
        try:
            # Copy file to container first, then upload to HDFS
            container_path = f"/tmp/{local_file.name}"
            
            # Copy file to namenode container
            copy_result = subprocess.run(
                ["docker", "cp", str(local_file), f"namenode-alt:{container_path}"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if copy_result.returncode != 0:
                logger.error(f"Failed to copy file to container: {copy_result.stderr}")
                return False
            
            # Build upload command for Docker
            cmd = ["docker", "exec", "namenode-alt", "hdfs", "dfs", "-put"]
            if overwrite:
                cmd.append("-f")  # Force overwrite
            cmd.extend([container_path, hdfs_path])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # Longer timeout for large files
            )
            
            # Clean up temporary file in container
            subprocess.run(
                ["docker", "exec", "namenode-alt", "rm", container_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Successfully uploaded {local_file.name}")
                return True
            else:
                logger.error(f"Upload failed for {local_file.name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Upload timeout for {local_file.name}")
            return False
        except Exception as e:
            logger.error(f"Upload error for {local_file.name}: {e}")
            return False
    
    def verify_hdfs_upload(self, hdfs_path: str, expected_size: Optional[int] = None) -> bool:
        """Verify file upload success in HDFS"""
        try:
            # Check if file exists and get details via Docker
            result = subprocess.run(
                ["docker", "exec", "namenode-alt", "hdfs", "dfs", "-ls", hdfs_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"File not found in HDFS: {hdfs_path}")
                return False
            
            # Parse file size from ls output
            ls_output = result.stdout.strip()
            if ls_output:
                # HDFS ls format: permissions user group size date time path
                parts = ls_output.split()
                if len(parts) >= 5:
                    hdfs_size = int(parts[4])
                    logger.info(f"HDFS file size: {hdfs_size:,} bytes")
                    
                    if expected_size is not None:
                        if abs(hdfs_size - expected_size) > 1000:  # Allow small variance
                            logger.warning(f"Size mismatch - Local: {expected_size:,}, HDFS: {hdfs_size:,}")
                            return False
            
            logger.info(f"✅ Verified file in HDFS: {hdfs_path}")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed for {hdfs_path}: {e}")
            return False
    
    def upload_dataset_to_hdfs(self) -> Dict:
        """Upload all dataset files to HDFS"""
        logger.info("Starting HDFS dataset upload...")
        
        upload_results = {
            'upload_date': datetime.now().isoformat(),
            'total_files': len(self.upload_files),
            'successful_uploads': 0,
            'failed_uploads': 0,
            'files': {}
        }
        
        for file_key, local_file in self.upload_files.items():
            if not local_file.exists():
                logger.warning(f"Skipping missing file: {local_file}")
                upload_results['files'][file_key] = {
                    'status': 'skipped',
                    'reason': 'file_not_found'
                }
                continue
            
            # Determine HDFS destination
            if 'metadata' in file_key or 'raw' in file_key:
                hdfs_dir = f"{self.hdfs_raw_path}/metr_la"
            else:
                hdfs_dir = f"{self.hdfs_processed_path}/metr_la"
            
            hdfs_file_path = f"{hdfs_dir}/{local_file.name}"
            
            # Get local file size
            local_size = local_file.stat().st_size
            
            # Upload file
            upload_success = self.upload_file_to_hdfs(local_file, hdfs_file_path)
            
            if upload_success:
                # Verify upload
                verify_success = self.verify_hdfs_upload(hdfs_file_path, local_size)
                
                if verify_success:
                    upload_results['successful_uploads'] += 1
                    upload_results['files'][file_key] = {
                        'status': 'success',
                        'local_file': str(local_file),
                        'hdfs_path': hdfs_file_path,
                        'file_size': local_size
                    }
                    logger.info(f"✅ Complete: {file_key}")
                else:
                    upload_results['failed_uploads'] += 1
                    upload_results['files'][file_key] = {
                        'status': 'verification_failed',
                        'local_file': str(local_file),
                        'hdfs_path': hdfs_file_path
                    }
            else:
                upload_results['failed_uploads'] += 1
                upload_results['files'][file_key] = {
                    'status': 'upload_failed',
                    'local_file': str(local_file),
                    'hdfs_path': hdfs_file_path
                }
        
        return upload_results
    
    def generate_hdfs_data_inventory(self) -> Dict:
        """Generate inventory of data in HDFS"""
        logger.info("Generating HDFS data inventory...")
        
        inventory = {
            'inventory_date': datetime.now().isoformat(),
            'hdfs_base_path': self.hdfs_base_path,
            'directories': {},
            'total_files': 0,
            'total_size_bytes': 0
        }
        
        try:
            # Check each directory
            for directory in [self.hdfs_raw_path, self.hdfs_processed_path]:
                dir_name = directory.split('/')[-1]
                inventory['directories'][dir_name] = {
                    'path': directory,
                    'files': [],
                    'file_count': 0,
                    'total_size': 0
                }
                
                # List files in directory recursively via Docker
                result = subprocess.run(
                    ["docker", "exec", "namenode-alt", "hdfs", "dfs", "-ls", "-R", directory],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line and not line.startswith('d'):  # Skip directories
                            parts = line.split()
                            if len(parts) >= 8:
                                permissions = parts[0]
                                size = int(parts[4])
                                date = parts[5]
                                time = parts[6]
                                path = parts[7]
                                
                                file_info = {
                                    'path': path,
                                    'size': size,
                                    'date': date,
                                    'time': time,
                                    'permissions': permissions
                                }
                                
                                inventory['directories'][dir_name]['files'].append(file_info)
                                inventory['directories'][dir_name]['total_size'] += size
                                inventory['total_size_bytes'] += size
                                inventory['total_files'] += 1
                    
                    inventory['directories'][dir_name]['file_count'] = len(inventory['directories'][dir_name]['files'])
        
        except Exception as e:
            logger.error(f"Error generating inventory: {e}")
        
        return inventory
    
    def create_data_access_script(self) -> None:
        """Create convenience script for accessing HDFS data"""
        script_content = f'''#!/bin/bash
# HDFS Data Access Script for METR-LA Traffic Dataset
# Generated: {datetime.now().isoformat()}

echo "=== METR-LA Traffic Dataset HDFS Access ==="
echo "Base Path: {self.hdfs_base_path}"
echo ""

# List all data files
echo "📁 Available Data Files:"
docker exec namenode-alt hdfs dfs -ls -h -R {self.hdfs_base_path}

echo ""
echo "🔍 Quick Data Overview:"

# Show raw data files
echo "Raw Data Files:"
docker exec namenode-alt hdfs dfs -ls -h {self.hdfs_raw_path}/metr_la/

# Show processed data files  
echo "Processed Data Files:"
docker exec namenode-alt hdfs dfs -ls -h {self.hdfs_processed_path}/metr_la/

echo ""
echo "📊 Sample Data Preview (first 10 lines):"
echo "--- Sensor Metadata ---"
docker exec namenode-alt hdfs dfs -cat {self.hdfs_raw_path}/metr_la/metr_la_sensor_metadata.csv | head -n 10

echo ""
echo "--- Processed Traffic Data ---"
docker exec namenode-alt hdfs dfs -cat {self.hdfs_processed_path}/metr_la/metr_la_essential_features.csv | head -n 10

echo ""
echo "💡 Usage Examples:"
echo "# Copy file from HDFS to local:"
echo "docker exec namenode-alt hdfs dfs -get {self.hdfs_processed_path}/metr_la/metr_la_ml_ready.csv /tmp/local_file.csv"
echo "docker cp namenode-alt:/tmp/local_file.csv ./local_file.csv"
echo ""
echo "# View file contents:"
echo "docker exec namenode-alt hdfs dfs -cat {self.hdfs_raw_path}/metr_la/preprocessing_metadata.json"
echo ""
echo "# Check file size:"
echo "docker exec namenode-alt hdfs dfs -du -h {self.hdfs_processed_path}/metr_la/"
'''
        
        script_file = Path("scripts/hdfs-data-access.sh")
        with open(script_file, 'w') as f:
            f.write(script_content)
        
        # Make script executable
        script_file.chmod(script_file.stat().st_mode | 0o755)
        logger.info(f"✅ Created data access script: {script_file}")
    
    def save_upload_metadata(self, upload_results: Dict, inventory: Dict) -> None:
        """Save upload metadata and results"""
        metadata = {
            'hdfs_upload_metadata': {
                'upload_date': datetime.now().isoformat(),
                'uploader_version': '1.0',
                'hdfs_configuration': {
                    'base_path': self.hdfs_base_path,
                    'raw_path': self.hdfs_raw_path,
                    'processed_path': self.hdfs_processed_path
                }
            },
            'upload_results': upload_results,
            'hdfs_inventory': inventory,
            'data_access_info': {
                'raw_sensor_metadata': f"{self.hdfs_raw_path}/metr_la/metr_la_sensor_metadata.csv",
                'raw_traffic_data': f"{self.hdfs_raw_path}/metr_la/metr_la_sample_data.csv",
                'processed_full': f"{self.hdfs_processed_path}/metr_la/metr_la_processed_data.csv",
                'processed_essential': f"{self.hdfs_processed_path}/metr_la/metr_la_essential_features.csv",
                'ml_ready': f"{self.hdfs_processed_path}/metr_la/metr_la_ml_ready.csv",
                'preprocessing_info': f"{self.hdfs_processed_path}/metr_la/preprocessing_metadata.json"
            }
        }
        
        metadata_file = self.processed_dir / "hdfs_upload_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"✅ Upload metadata saved: {metadata_file}")
    
    def upload_dataset(self) -> bool:
        """Main upload process"""
        try:
            logger.info("Starting HDFS dataset upload process...")
            
            # Check Hadoop status
            if not self.check_hadoop_status():
                logger.error("Hadoop not available - cannot proceed with upload")
                return False
            
            # Create directories
            if not self.create_hdfs_directories():
                logger.error("Failed to create HDFS directories")
                return False
            
            # Upload files
            upload_results = self.upload_dataset_to_hdfs()
            
            # Generate inventory
            inventory = self.generate_hdfs_data_inventory()
            
            # Create access script
            self.create_data_access_script()
            
            # Save metadata
            self.save_upload_metadata(upload_results, inventory)
            
            # Report results
            success_rate = upload_results['successful_uploads'] / upload_results['total_files'] * 100
            logger.info(f"✅ Upload complete - {upload_results['successful_uploads']}/{upload_results['total_files']} files ({success_rate:.1f}%)")
            
            if upload_results['failed_uploads'] > 0:
                logger.warning(f"⚠️  {upload_results['failed_uploads']} files failed to upload")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Upload process failed: {e}")
            return False

def main():
    """Main execution function"""
    print("=== HDFS Data Upload System (Task 6.4) ===")
    print("Traffic Prediction System - Upload METR-LA Dataset to HDFS\\n")
    
    try:
        # Initialize uploader
        uploader = HDFSUploader()
        
        # Upload dataset
        success = uploader.upload_dataset()
        
        if success:
            print("\\n✅ HDFS dataset upload completed successfully!")
            print(f"📁 Data uploaded to HDFS: {uploader.hdfs_base_path}")
            print("🔍 Use scripts/hdfs-data-access.sh to explore the data")
            print("📊 Check hdfs_upload_metadata.json for detailed upload information")
            return True
        else:
            print("\\n❌ HDFS dataset upload failed!")
            return False
            
    except Exception as e:
        print(f"\\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)