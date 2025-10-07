#!/usr/bin/env python3
"""
Kafka Producer for Test Scenarios

Produces traffic events from test scenario files to Kafka topics.
Supports configurable rate limiting and scenario selection.

Usage:
    python kafka_producer.py --scenario all --rate 10
    python kafka_producer.py --scenario scenario_1_normal_traffic --rate 100
"""

import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9094']
TRAFFIC_EVENTS_TOPIC = 'traffic-events'
TRAFFIC_RAW_TOPIC = 'traffic-raw'

class TrafficEventProducer:
    """Produces traffic events to Kafka topics"""
    
    def __init__(self, bootstrap_servers: List[str]):
        """Initialize Kafka producer with JSON serialization"""
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            # Connection settings
            api_version=(0, 10, 1),
            request_timeout_ms=30000,
            metadata_max_age_ms=300000,
            # Reliability settings
            acks='all',  # Wait for all replicas
            retries=3,
            max_in_flight_requests_per_connection=1,  # Ensure ordering
            # Performance settings  
            # compression_type='snappy',  # Disabled - requires python-snappy library
            batch_size=16384,
            linger_ms=10
        )
        self.stats = {
            'total_sent': 0,
            'total_failed': 0,
            'start_time': None,
            'end_time': None
        }
    
    def produce_event(self, topic: str, event: Dict[str, Any], key: str = None) -> bool:
        """
        Produce a single event to Kafka
        
        Args:
            topic: Kafka topic name
            event: Event data dict
            key: Optional partition key (sensor_id)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use sensor_id as partition key for co-located sensor data
            partition_key = key or event.get('sensor_id', 'default')
            
            # Send to Kafka
            future = self.producer.send(
                topic,
                value=event,
                key=partition_key
            )
            
            # Wait for acknowledgment (with timeout)
            record_metadata = future.get(timeout=10)
            
            self.stats['total_sent'] += 1
            return True
            
        except KafkaError as e:
            print(f"❌ Kafka error producing event: {e}")
            self.stats['total_failed'] += 1
            return False
        except Exception as e:
            print(f"❌ Unexpected error producing event: {e}")
            self.stats['total_failed'] += 1
            return False
    
    def produce_from_file(
        self,
        file_path: Path,
        topic: str,
        rate_limit: float = 10.0,
        max_events: int = None
    ) -> Dict[str, int]:
        """
        Produce events from a JSONL file to Kafka
        
        Args:
            file_path: Path to JSONL scenario file
            topic: Kafka topic to produce to
            rate_limit: Events per second (0 = unlimited)
            max_events: Maximum events to send (None = all)
        
        Returns:
            Statistics dict
        """
        print(f"\n{'='*70}")
        print(f"PRODUCING: {file_path.name}")
        print(f"{'='*70}")
        print(f"Topic: {topic}")
        print(f"Rate limit: {rate_limit} msg/sec" if rate_limit > 0 else "Rate limit: Unlimited")
        if max_events:
            print(f"Max events: {max_events}")
        print()
        
        events_sent = 0
        events_failed = 0
        start_time = time.time()
        self.stats['start_time'] = datetime.now()
        
        # Calculate delay between messages
        delay = 1.0 / rate_limit if rate_limit > 0 else 0
        
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                # Check max events limit
                if max_events and events_sent >= max_events:
                    print(f"\n✓ Reached max events limit ({max_events})")
                    break
                
                try:
                    # Parse event
                    event = json.loads(line.strip())
                    
                    # Produce to Kafka
                    success = self.produce_event(topic, event)
                    
                    if success:
                        events_sent += 1
                        
                        # Progress indicator every 100 events
                        if events_sent % 100 == 0:
                            elapsed = time.time() - start_time
                            current_rate = events_sent / elapsed if elapsed > 0 else 0
                            print(f"  Sent {events_sent} events ({current_rate:.1f} msg/sec)")
                        
                        # Rate limiting
                        if delay > 0:
                            time.sleep(delay)
                    else:
                        events_failed += 1
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️  Line {line_num}: Invalid JSON - {e}")
                    events_failed += 1
                except Exception as e:
                    print(f"⚠️  Line {line_num}: Unexpected error - {e}")
                    events_failed += 1
        
        # Final stats
        self.stats['end_time'] = datetime.now()
        elapsed = time.time() - start_time
        actual_rate = events_sent / elapsed if elapsed > 0 else 0
        
        print(f"\n{'='*70}")
        print(f"SUMMARY: {file_path.name}")
        print(f"{'='*70}")
        print(f"✓ Total sent: {events_sent}")
        print(f"✗ Total failed: {events_failed}")
        print(f"⏱  Duration: {elapsed:.1f} seconds")
        print(f"📊 Actual rate: {actual_rate:.1f} msg/sec")
        print()
        
        return {
            'file': file_path.name,
            'sent': events_sent,
            'failed': events_failed,
            'duration': elapsed,
            'rate': actual_rate
        }
    
    def flush_and_close(self):
        """Flush pending messages and close producer"""
        print("Flushing pending messages...")
        self.producer.flush()
        self.producer.close()
        print("✓ Producer closed")


def load_scenarios(scenarios_dir: Path, scenario_filter: str = 'all') -> List[Path]:
    """
    Load scenario files based on filter
    
    Args:
        scenarios_dir: Directory containing scenario files
        scenario_filter: 'all' or specific scenario name
    
    Returns:
        List of scenario file paths
    """
    if scenario_filter == 'all':
        scenarios = sorted(scenarios_dir.glob("scenario_*.jsonl"))
    else:
        # Check if filter is a scenario name or file
        if scenario_filter.endswith('.jsonl'):
            scenario_file = scenarios_dir / scenario_filter
        else:
            scenario_file = scenarios_dir / f"{scenario_filter}.jsonl"
        
        if scenario_file.exists():
            scenarios = [scenario_file]
        else:
            print(f"❌ Scenario not found: {scenario_filter}")
            print(f"Looking in: {scenarios_dir}")
            return []
    
    return scenarios


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Produce traffic events from test scenarios to Kafka'
    )
    parser.add_argument(
        '--scenario',
        default='all',
        help='Scenario to produce: "all" or scenario name (default: all)'
    )
    parser.add_argument(
        '--topic',
        default=TRAFFIC_RAW_TOPIC,
        choices=[TRAFFIC_EVENTS_TOPIC, TRAFFIC_RAW_TOPIC],
        help=f'Kafka topic (default: {TRAFFIC_RAW_TOPIC})'
    )
    parser.add_argument(
        '--rate',
        type=float,
        default=10.0,
        help='Messages per second (0 = unlimited, default: 10)'
    )
    parser.add_argument(
        '--max',
        type=int,
        help='Maximum events to send per file (default: all)'
    )
    parser.add_argument(
        '--scenarios-dir',
        type=Path,
        default=Path('data/test_scenarios'),
        help='Directory containing scenario files (default: data/test_scenarios)'
    )
    
    args = parser.parse_args()
    
    # Validate scenarios directory
    if not args.scenarios_dir.exists():
        print(f"❌ Scenarios directory not found: {args.scenarios_dir}")
        print("Run generate_test_scenarios.py first")
        return 1
    
    # Load scenarios
    scenarios = load_scenarios(args.scenarios_dir, args.scenario)
    if not scenarios:
        return 1
    
    print("=" * 70)
    print("KAFKA PRODUCER - TRAFFIC TEST SCENARIOS")
    print("=" * 70)
    print(f"Bootstrap servers: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Target topic: {args.topic}")
    print(f"Scenarios to produce: {len(scenarios)}")
    print(f"Rate limit: {args.rate} msg/sec" if args.rate > 0 else "Rate limit: Unlimited")
    if args.max:
        print(f"Max events per file: {args.max}")
    print()
    
    # Initialize producer
    try:
        producer = TrafficEventProducer(KAFKA_BOOTSTRAP_SERVERS)
    except Exception as e:
        print(f"❌ Failed to initialize Kafka producer: {e}")
        print("\nTroubleshooting:")
        print("1. Verify Kafka broker is running: docker ps | grep kafka")
        print("2. Check Kafka port 9094 is accessible")
        print("3. Check network connectivity")
        return 1
    
    # Produce scenarios
    all_results = []
    try:
        for scenario_file in scenarios:
            result = producer.produce_from_file(
                scenario_file,
                args.topic,
                rate_limit=args.rate,
                max_events=args.max
            )
            all_results.append(result)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        producer.flush_and_close()
    
    # Overall summary
    print("=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)
    total_sent = sum(r['sent'] for r in all_results)
    total_failed = sum(r['failed'] for r in all_results)
    total_duration = sum(r['duration'] for r in all_results)
    overall_rate = total_sent / total_duration if total_duration > 0 else 0
    
    print(f"\nTotal events sent: {total_sent}")
    print(f"Total events failed: {total_failed}")
    print(f"Total duration: {total_duration:.1f} seconds")
    print(f"Overall rate: {overall_rate:.1f} msg/sec")
    
    print(f"\nPer-Scenario Results:")
    for result in all_results:
        status = "✅" if result['failed'] == 0 else "⚠️"
        print(f"  {status} {result['file']}: {result['sent']} sent ({result['rate']:.1f} msg/sec)")
    
    if total_failed == 0:
        print(f"\n✅ SUCCESS: All {total_sent} events produced successfully!")
        return 0
    else:
        print(f"\n⚠️  WARNING: {total_failed} events failed to produce")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
