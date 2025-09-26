#!/usr/bin/env python3
"""
METR-LA Traffic Producer Integration Demo - Task 8
Demonstrates the complete producer setup and data streaming workflow.
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Add producer to path
sys.path.insert(0, os.path.dirname(__file__))

from traffic_producer import TrafficDataProducer, ProducerConfig, load_config_from_file, create_default_config_file


def check_prerequisites():
    """Check if required data files and dependencies exist"""
    print("Checking prerequisites...")
    
    # Check if we're in the right directory
    repo_root = Path(__file__).parent.parent.parent
    data_dir = repo_root / 'data' / 'raw'
    
    required_files = [
        data_dir / 'metr_la_sample_data.csv',
        data_dir / 'metr_la_sensor_metadata.csv'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not file_path.exists():
            missing_files.append(str(file_path))
        else:
            # Get file size for display
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"✓ Found {file_path.name} ({size_mb:.1f} MB)")
    
    if missing_files:
        print("\n❌ Missing required data files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        print("\nPlease ensure METR-LA data files are downloaded.")
        return False
    
    # Check Kafka dependency
    try:
        import kafka
        print("✓ kafka-python library available")
    except ImportError:
        print("❌ kafka-python library not found")
        print("Install with: pip install kafka-python==2.0.2")
        return False
    
    return True


def create_demo_config():
    """Create demonstration configuration"""
    print("\nCreating demo configuration...")
    
    config_file = 'demo_producer_config.ini'
    
    if os.path.exists(config_file):
        print(f"✓ Configuration file {config_file} already exists")
    else:
        create_default_config_file(config_file)
        print(f"✓ Created {config_file}")
    
    # Load and display configuration
    config = load_config_from_file(config_file)
    
    print(f"\nDemo Configuration:")
    print(f"  - Kafka Servers: {config.kafka_bootstrap_servers}")
    print(f"  - Topic: {config.topic_name}")
    print(f"  - Data File: {config.data_file}")
    print(f"  - Replay Speed: {config.replay_speed}x")
    print(f"  - Batch Size: {config.batch_size}")
    print(f"  - Health Port: {config.health_check_port}")
    
    return config


def run_data_analysis(config):
    """Analyze the METR-LA data before streaming"""
    print("\nAnalyzing METR-LA data...")
    
    producer = TrafficDataProducer(config)
    
    try:
        # Load sensor metadata
        producer.load_sensor_metadata()
        
        print(f"✓ Loaded metadata for {len(producer.sensor_metadata)} sensors")
        
        # Analyze CSV data
        import csv
        with open(config.data_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            row_count = 0
            speed_values = []
            volume_values = []
            
            for row in reader:
                row_count += 1
                
                if row['speed_mph']:
                    try:
                        speed_values.append(float(row['speed_mph']))
                    except ValueError:
                        pass
                
                if row['volume_vehicles_per_hour']:
                    try:
                        volume_values.append(float(row['volume_vehicles_per_hour']))
                    except ValueError:
                        pass
                
                # Limit analysis to first 10000 rows for performance
                if row_count >= 10000:
                    break
        
        print(f"✓ Data Analysis Results:")
        print(f"  - Total Records: {row_count}+")
        print(f"  - Speed Data Points: {len(speed_values)}")
        print(f"  - Volume Data Points: {len(volume_values)}")
        
        if speed_values:
            avg_speed = sum(speed_values) / len(speed_values)
            print(f"  - Average Speed: {avg_speed:.1f} mph")
        
        if volume_values:
            avg_volume = sum(volume_values) / len(volume_values)
            print(f"  - Average Volume: {avg_volume:.0f} vph")
        
        return True
        
    except Exception as e:
        print(f"❌ Data analysis failed: {e}")
        return False


def run_mock_demo():
    """Run a demonstration without requiring Kafka"""
    print("\n" + "="*60)
    print("MOCK DEMONSTRATION MODE")
    print("="*60)
    
    print("\n🚀 This demonstrates the producer workflow without Kafka")
    print("📊 In production, messages would be sent to Kafka topic")
    
    # Create a mock configuration
    config = ProducerConfig(
        kafka_bootstrap_servers="localhost:9092",
        topic_name="traffic-raw",
        data_file="../../data/raw/metr_la_sample_data.csv",
        metadata_file="../../data/raw/metr_la_sensor_metadata.csv",
        replay_speed=10.0,  # 10x speed for demo
        batch_size=10,
        max_records=50  # Limit for demo
    )
    
    producer = TrafficDataProducer(config)
    
    try:
        # Load metadata
        print("\n1. Loading sensor metadata...")
        producer.load_sensor_metadata()
        print(f"   ✓ Loaded {len(producer.sensor_metadata)} sensors")
        
        # Demonstrate CSV processing
        print("\n2. Processing CSV data...")
        
        import csv
        with open(config.data_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for i, row in enumerate(reader):
                if i >= 5:  # Process only first 5 rows for demo
                    break
                    
                event = producer.convert_csv_row_to_event(row, i)
                
                print(f"\n   Record {i+1}:")
                print(f"     Event ID: {event.event_id}")
                print(f"     Segment: {event.segment_id}")
                print(f"     Speed: {event.speed:.1f} km/h" if event.speed else "     Speed: N/A")
                print(f"     Volume: {event.volume} vph" if event.volume else "     Volume: N/A")
                print(f"     Quality: {event.quality_score:.2f}")
                
                # Simulate message sending
                print(f"     📤 Would send to topic: {config.topic_name}")
        
        print(f"\n3. Metrics simulation...")
        producer.metrics.record_success(1000)
        producer.metrics.record_success(1200)
        producer.metrics.record_failure()
        
        stats = producer.metrics.get_stats()
        print(f"     Messages Sent: {stats['messages_sent']}")
        print(f"     Messages Failed: {stats['messages_failed']}")
        print(f"     Success Rate: {stats['success_rate']:.1%}")
        
        print(f"\n✅ Mock demonstration completed successfully!")
        print(f"💡 To run with real Kafka, ensure Kafka is running and remove --mock flag")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return False
    
    return True


def main():
    """Main demonstration function"""
    parser = argparse.ArgumentParser(description='METR-LA Traffic Producer Integration Demo')
    parser.add_argument('--mock', action='store_true', help='Run mock demonstration without Kafka')
    parser.add_argument('--config', '-c', default='demo_producer_config.ini', help='Configuration file path')
    parser.add_argument('--max-records', '-m', type=int, default=100, help='Maximum records for demo')
    
    args = parser.parse_args()
    
    print("METR-LA Traffic Data Producer - Integration Demo")
    print("="*50)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please resolve issues above.")
        return 1
    
    # Run mock demonstration if requested
    if args.mock:
        return 0 if run_mock_demo() else 1
    
    # Create configuration
    config = create_demo_config()
    
    # Override max records for demo
    if args.max_records:
        config.max_records = args.max_records
    
    # Analyze data
    if not run_data_analysis(config):
        return 1
    
    print(f"\n" + "="*60)
    print("READY TO STREAM DATA")
    print("="*60)
    
    print(f"\n📋 Demo Configuration:")
    print(f"   - Will stream up to {config.max_records or 'unlimited'} records")
    print(f"   - Replay speed: {config.replay_speed}x")
    print(f"   - Batch size: {config.batch_size}")
    print(f"   - Target topic: {config.topic_name}")
    
    print(f"\n🚀 Starting producer in 3 seconds...")
    print(f"   Press Ctrl+C to stop gracefully")
    print(f"   Monitor at: http://localhost:{config.health_check_port}/health")
    
    time.sleep(3)
    
    # Initialize and run producer
    producer = TrafficDataProducer(config)
    
    try:
        print(f"\n" + "-"*50)
        producer.logger.info("Starting METR-LA Traffic Producer Demo...")
        
        # Load metadata and initialize producer
        producer.load_sensor_metadata()
        producer.initialize_producer()
        
        # Start streaming
        producer.start_streaming()
        
        print(f"\n✅ Demo completed successfully!")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Demo stopped by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        return 1
    finally:
        if producer.producer:
            producer.producer.close()
        producer.stop_health_server()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())