#!/usr/bin/env python3
"""
METR-LA CSV Data Ingestion System
Robust CSV reader that loads METR-LA dataset with proper validation,
preprocessing, and streaming capabilities for Kafka integration
"""

import csv
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Iterator, Any
from pathlib import Path
import argparse
import sys
import time
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metr_la_ingestion")

@dataclass
class TrafficRecord:
    """Structured traffic record for METR-LA data"""
    timestamp: str
    sensor_id: str
    speed_mph: Optional[float]
    volume_vehicles_per_hour: Optional[float]
    latitude: float
    longitude: float
    road_type: str
    road_name: str
    direction: str
    data_quality: float = 1.0
    ingestion_timestamp: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization processing"""
        if self.ingestion_timestamp is None:
            self.ingestion_timestamp = datetime.now().isoformat()

@dataclass
class IngestionConfig:
    """Configuration for CSV data ingestion"""
    csv_file_path: str
    chunk_size: int = 1000
    validate_data: bool = True
    handle_missing_values: bool = True
    time_column: str = "timestamp"
    numeric_columns: Optional[List[str]] = None
    required_columns: Optional[List[str]] = None
    output_format: str = "json"  # json, avro, parquet
    max_records: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    quality_threshold: float = 0.5
    
    def __post_init__(self):
        if self.numeric_columns is None:
            self.numeric_columns = ["speed_mph", "volume_vehicles_per_hour", "latitude", "longitude"]
        if self.required_columns is None:
            self.required_columns = ["timestamp", "sensor_id", "latitude", "longitude"]

class MetrLACSVIngestion:
    """METR-LA CSV data ingestion system with validation and streaming"""
    
    def __init__(self, config: IngestionConfig):
        """Initialize the ingestion system"""
        self.config = config
        self.processed_count = 0
        self.valid_count = 0
        self.invalid_count = 0
        self.missing_value_count = 0
        self.data_quality_stats = {}
        
        # Validate CSV file exists
        if not Path(config.csv_file_path).exists():
            raise FileNotFoundError(f"CSV file not found: {config.csv_file_path}")
            
        logger.info(f"Initialized METR-LA CSV ingestion for: {config.csv_file_path}")
    
    def validate_record(self, record: Dict[str, Any]) -> tuple[bool, float, str]:
        """
        Validate a single traffic record
        Returns: (is_valid, quality_score, validation_message)
        """
        issues = []
        quality_score = 1.0
        
        # Check required columns
        for col in (self.config.required_columns or []):
            if col not in record or record[col] is None or str(record[col]).strip() == '':
                issues.append(f"Missing required column: {col}")
                quality_score -= 0.3
        
        # Validate timestamp format
        try:
            if 'timestamp' in record and record['timestamp']:
                pd.to_datetime(record['timestamp'])
        except (ValueError, TypeError):
            issues.append("Invalid timestamp format")
            quality_score -= 0.2
        
        # Validate numeric columns
        for col in (self.config.numeric_columns or []):
            if col in record and record[col] is not None and str(record[col]).strip():
                try:
                    value = float(record[col])
                    # Check for reasonable ranges
                    if col == "speed_mph" and (value < 0 or value > 120):
                        issues.append(f"Speed out of reasonable range: {value}")
                        quality_score -= 0.1
                    elif col == "volume_vehicles_per_hour" and (value < 0 or value > 10000):
                        issues.append(f"Volume out of reasonable range: {value}")
                        quality_score -= 0.1
                    elif col in ["latitude", "longitude"]:
                        if col == "latitude" and not (32.0 <= value <= 35.0):  # LA area
                            issues.append(f"Latitude out of LA range: {value}")
                            quality_score -= 0.2
                        elif col == "longitude" and not (-120.0 <= value <= -117.0):  # LA area
                            issues.append(f"Longitude out of LA range: {value}")
                            quality_score -= 0.2
                except (ValueError, TypeError):
                    issues.append(f"Invalid numeric value in {col}: {record[col]}")
                    quality_score -= 0.1
        
        # Check for missing critical traffic data
        if not record.get('speed_mph') and not record.get('volume_vehicles_per_hour'):
            issues.append("Both speed and volume are missing")
            quality_score -= 0.3
        
        is_valid = quality_score >= self.config.quality_threshold and len(issues) == 0
        validation_message = "; ".join(issues) if issues else "Valid"
        
        return is_valid, max(0.0, quality_score), validation_message
    
    def handle_missing_values(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Handle missing values in the record"""
        if not self.config.handle_missing_values:
            return record
        
        # Convert empty strings to None
        for key, value in record.items():
            if isinstance(value, str) and value.strip() == '':
                record[key] = None
        
        # For numeric columns, handle missing values based on context
        if record.get('speed_mph') is None and record.get('volume_vehicles_per_hour') is not None:
            # If we have volume but no speed, estimate based on typical traffic patterns
            volume = float(record['volume_vehicles_per_hour'])
            if volume < 50:
                record['speed_mph'] = 45.0  # Low volume, higher speed
            elif volume < 200:
                record['speed_mph'] = 35.0  # Medium volume
            else:
                record['speed_mph'] = 25.0  # High volume, lower speed
            self.missing_value_count += 1
        
        elif record.get('volume_vehicles_per_hour') is None and record.get('speed_mph') is not None:
            # If we have speed but no volume, estimate based on speed
            speed = float(record['speed_mph'])
            if speed > 40:
                record['volume_vehicles_per_hour'] = 100.0  # High speed, medium volume
            elif speed > 25:
                record['volume_vehicles_per_hour'] = 200.0  # Medium speed, higher volume
            else:
                record['volume_vehicles_per_hour'] = 300.0  # Low speed, high congestion
            self.missing_value_count += 1
        
        return record
    
    def process_record(self, raw_record: Dict[str, Any]) -> Optional[TrafficRecord]:
        """Process a single raw CSV record into a TrafficRecord"""
        try:
            # Handle missing values first
            processed_record = self.handle_missing_values(raw_record.copy())
            
            # Validate the record
            if self.config.validate_data:
                is_valid, quality_score, validation_msg = self.validate_record(processed_record)
                if not is_valid:
                    logger.debug(f"Invalid record: {validation_msg}")
                    self.invalid_count += 1
                    return None
            else:
                quality_score = 1.0
            
            # Convert to structured record
            timestamp_val = processed_record.get('timestamp', '')
            if hasattr(timestamp_val, 'isoformat'):
                timestamp_str = timestamp_val.isoformat()
            else:
                timestamp_str = str(timestamp_val)
            
            traffic_record = TrafficRecord(
                timestamp=timestamp_str,
                sensor_id=processed_record.get('sensor_id', ''),
                speed_mph=float(processed_record['speed_mph']) if processed_record.get('speed_mph') is not None else None,
                volume_vehicles_per_hour=float(processed_record['volume_vehicles_per_hour']) if processed_record.get('volume_vehicles_per_hour') is not None else None,
                latitude=float(processed_record['latitude']),
                longitude=float(processed_record['longitude']),
                road_type=processed_record.get('road_type', ''),
                road_name=processed_record.get('road_name', ''),
                direction=processed_record.get('direction', ''),
                data_quality=quality_score
            )
            
            self.valid_count += 1
            return traffic_record
            
        except Exception as e:
            logger.warning(f"Error processing record: {e}")
            self.invalid_count += 1
            return None
    
    def read_csv_stream(self) -> Iterator[TrafficRecord]:
        """Stream CSV records with chunked processing"""
        logger.info(f"Starting CSV stream processing with chunk size: {self.config.chunk_size}")
        
        try:
            # Read CSV in chunks for memory efficiency
            chunk_iter = pd.read_csv(
                self.config.csv_file_path,
                chunksize=self.config.chunk_size,
                parse_dates=[self.config.time_column] if self.config.time_column else None
            )
            
            for chunk_num, chunk in enumerate(chunk_iter):
                logger.debug(f"Processing chunk {chunk_num + 1} with {len(chunk)} records")
                
                # Filter by date range if specified
                if self.config.start_date or self.config.end_date:
                    chunk[self.config.time_column] = pd.to_datetime(chunk[self.config.time_column])
                    if self.config.start_date:
                        chunk = chunk[chunk[self.config.time_column] >= pd.to_datetime(self.config.start_date)]
                    if self.config.end_date:
                        chunk = chunk[chunk[self.config.time_column] <= pd.to_datetime(self.config.end_date)]
                
                # Process each record in the chunk
                for _, row in chunk.iterrows():
                    # Check max records limit
                    if self.config.max_records and self.processed_count >= self.config.max_records:
                        logger.info(f"Reached max records limit: {self.config.max_records}")
                        return
                    
                    record = row.to_dict()
                    processed_record = self.process_record(record)
                    
                    if processed_record:
                        self.processed_count += 1
                        yield processed_record
                        
                        # Log progress
                        if self.processed_count % 1000 == 0:
                            logger.info(f"Processed {self.processed_count} records "
                                      f"(Valid: {self.valid_count}, Invalid: {self.invalid_count})")
                
        except Exception as e:
            logger.error(f"Error reading CSV stream: {e}")
            raise
    
    def read_all_records(self) -> List[TrafficRecord]:
        """Read all records into memory (use for smaller datasets)"""
        logger.info("Reading all records into memory")
        
        records = []
        for record in self.read_csv_stream():
            records.append(record)
        
        logger.info(f"Loaded {len(records)} records into memory")
        return records
    
    def export_to_json(self, output_file: str, records: Optional[List[TrafficRecord]] = None) -> None:
        """Export records to JSON file"""
        if records is None:
            records = self.read_all_records()
        
        logger.info(f"Exporting {len(records)} records to JSON: {output_file}")
        
        with open(output_file, 'w') as f:
            for record in records:
                json.dump(asdict(record), f)
                f.write('\n')  # JSONL format
        
        logger.info("JSON export completed")
    
    def export_to_parquet(self, output_file: str, records: Optional[List[TrafficRecord]] = None) -> None:
        """Export records to Parquet file"""
        if records is None:
            records = self.read_all_records()
        
        logger.info(f"Exporting {len(records)} records to Parquet: {output_file}")
        
        # Convert to DataFrame
        data = [asdict(record) for record in records]
        df = pd.DataFrame(data)
        
        # Convert timestamp columns to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['ingestion_timestamp'] = pd.to_datetime(df['ingestion_timestamp'])
        
        # Save as Parquet
        df.to_parquet(output_file, index=False)
        
        logger.info("Parquet export completed")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        total_processed = self.valid_count + self.invalid_count
        
        stats = {
            'total_processed': total_processed,
            'valid_records': self.valid_count,
            'invalid_records': self.invalid_count,
            'missing_values_handled': self.missing_value_count,
            'validation_rate': (self.valid_count / total_processed) if total_processed > 0 else 0,
            'data_quality_average': self.valid_count / total_processed if total_processed > 0 else 0,
            'ingestion_timestamp': datetime.now().isoformat()
        }
        
        return stats
    
    def print_summary(self):
        """Print ingestion summary"""
        stats = self.get_statistics()
        
        print("\n" + "=" * 60)
        print("METR-LA CSV INGESTION SUMMARY")
        print("=" * 60)
        print(f"Total records processed: {stats['total_processed']:,}")
        print(f"Valid records: {stats['valid_records']:,}")
        print(f"Invalid records: {stats['invalid_records']:,}")
        print(f"Missing values handled: {stats['missing_values_handled']:,}")
        print(f"Validation rate: {stats['validation_rate']:.2%}")
        print(f"Average data quality: {stats['data_quality_average']:.2%}")
        print("=" * 60)

def create_sample_config() -> IngestionConfig:
    """Create a sample configuration"""
    return IngestionConfig(
        csv_file_path="data/raw/metr_la_sample_data.csv",
        chunk_size=1000,
        validate_data=True,
        handle_missing_values=True,
        max_records=10000,
        quality_threshold=0.5
    )

def main():
    """Main entry point for CSV ingestion"""
    parser = argparse.ArgumentParser(description='METR-LA CSV Data Ingestion')
    parser.add_argument('--csv-file', required=True, help='Path to METR-LA CSV file')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--format', choices=['json', 'parquet'], default='json', help='Output format')
    parser.add_argument('--chunk-size', type=int, default=1000, help='Chunk size for processing')
    parser.add_argument('--max-records', type=int, help='Maximum records to process')
    parser.add_argument('--start-date', help='Start date filter (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date filter (YYYY-MM-DD)')
    parser.add_argument('--quality-threshold', type=float, default=0.5, help='Quality threshold')
    parser.add_argument('--no-validation', action='store_true', help='Skip data validation')
    parser.add_argument('--no-missing-handling', action='store_true', help='Skip missing value handling')
    parser.add_argument('--validate', action='store_true', help='Run validation only')
    
    args = parser.parse_args()
    
    # Create configuration
    config = IngestionConfig(
        csv_file_path=args.csv_file,
        chunk_size=args.chunk_size,
        validate_data=not args.no_validation,
        handle_missing_values=not args.no_missing_handling,
        max_records=args.max_records,
        start_date=args.start_date,
        end_date=args.end_date,
        quality_threshold=args.quality_threshold,
        output_format=args.format
    )
    
    # Initialize ingestion system
    ingestion = MetrLACSVIngestion(config)
    
    try:
        print("🚀 Starting METR-LA CSV Data Ingestion")
        print(f"📁 Source: {args.csv_file}")
        print(f"📊 Chunk size: {args.chunk_size:,}")
        print(f"🎯 Quality threshold: {args.quality_threshold}")
        print("=" * 60)
        
        # Process data
        if args.output:
            if args.format == 'json':
                ingestion.export_to_json(args.output)
            elif args.format == 'parquet':
                ingestion.export_to_parquet(args.output)
        else:
            # Just process and show stats
            records = list(ingestion.read_csv_stream())
            logger.info(f"Processed {len(records)} records")
        
        # Show summary
        ingestion.print_summary()
        
        print("✅ CSV ingestion completed successfully!")
        
    except Exception as e:
        logger.error(f"CSV ingestion failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())