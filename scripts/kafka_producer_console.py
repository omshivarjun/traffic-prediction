#!/usr/bin/env python3
"""
Kafka Console Producer Wrapper for Test Scenarios

Uses the native kafka-console-producer tool inside the kafka-broker1 container
to avoid Python kafka-python connection issues with advertised listeners.

This is the most reliable method for producing to Kafka from the host.

Usage:
    python kafka_producer_console.py --scenario all --rate 10
    python kafka_producer_console.py --scenario scenario_1_normal_traffic --rate 100
"""

import argparse
import json
import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime

CONTAINER_NAME = 'kafka-broker1'
SCENARIOS_DIR = Path(__file__).parent.parent / 'data' / 'test_scenarios'

def check_container_running():
    """Verify kafka-broker1 container is running"""
    result = subprocess.run(
        ['docker', 'ps', '--filter', f'name={CONTAINER_NAME}', '--format', '{{.Names}}'],
        capture_output=True,
        text=True
    )
    return CONTAINER_NAME in result.stdout

def produce_scenario_file(file_path: Path, topic: str, rate_limit: float, max_events: int = None):
    """
    Produce events from a scenario file using kafka-console-producer.
    
    Args:
        file_path: Path to the scenario JSONL file
        topic: Kafka topic name
        rate_limit: Messages per second
        max_events: Maximum number of events to send (None = all)
    
    Returns:
        Tuple of (sent_count, failed_count)
    """
    print(f"\n{'='*70}")
    print(f"Producing: {file_path.name}")
    print(f"Topic: {topic}, Rate: {rate_limit} msg/sec, Max: {max_events or 'unlimited'}")
    print(f"{'='*70}")
    
    delay = 1.0 / rate_limit if rate_limit > 0 else 0
    
    sent = 0
    failed = 0
    start_time = datetime.now()
    
    # Read events from file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            events = [json.loads(line.strip()) for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading file: {e}")
        return 0, 1
    
    if max_events:
        events = events[:max_events]
    
    total_events = len(events)
    print(f"Loaded {total_events} events from {file_path.name}")
    
    # Produce events using kafka-console-producer
    # We'll send them in batches via stdin
    try:
        # Start the producer process
        cmd = [
            'docker', 'exec', '-i', CONTAINER_NAME,
            'kafka-console-producer',
            '--bootstrap-server', 'localhost:9092',
            '--topic', topic
        ]
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send events
        for i, event in enumerate(events, 1):
            try:
                # Convert event to JSON string and send
                json_str = json.dumps(event)
                process.stdin.write(json_str + '\n')
                process.stdin.flush()
                
                sent += 1
                
                # Progress update
                if sent % 100 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = sent / elapsed if elapsed > 0 else 0
                    print(f"  Progress: {sent}/{total_events} ({sent/total_events*100:.1f}%) "
                          f"- Rate: {rate:.1f} msg/sec")
                
                # Rate limiting
                if delay > 0:
                    time.sleep(delay)
                    
            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"  Error on event {i}: {e}")
        
        # Close stdin to signal we're done
        process.stdin.close()
        
        # Wait for process to complete
        process.wait(timeout=10)
        
        # Check for errors
        stderr = process.stderr.read()
        if stderr and 'ERROR' in stderr:
            print(f"  Warning: {stderr}")
            
    except KeyboardInterrupt:
        print(f"\n  Interrupted by user")
        if process:
            process.terminate()
    except Exception as e:
        print(f"  Error during production: {e}")
        failed += len(events) - sent
    
    # Final stats
    elapsed = (datetime.now() - start_time).total_seconds()
    success_rate = (sent / (sent + failed) * 100) if (sent + failed) > 0 else 0
    avg_rate = sent / elapsed if elapsed > 0 else 0
    
    print(f"\nResults:")
    print(f"  Total events:  {total_events}")
    print(f"  Sent:          {sent}")
    print(f"  Failed:        {failed}")
    print(f"  Success rate:  {success_rate:.1f}%")
    print(f"  Time elapsed:  {elapsed:.1f}s")
    print(f"  Average rate:  {avg_rate:.1f} msg/sec")
    
    return sent, failed

def main():
    parser = argparse.ArgumentParser(
        description='Produce test scenarios to Kafka using kafka-console-producer'
    )
    parser.add_argument('--scenario', default='all',
                       help='Scenario to produce: "all" or specific scenario name (default: all)')
    parser.add_argument('--topic', default='traffic-raw',
                       help='Kafka topic (default: traffic-raw)')
    parser.add_argument('--rate', type=float, default=10.0,
                       help='Messages per second (default: 10)')
    parser.add_argument('--max', type=int, default=None,
                       help='Maximum messages per scenario (default: unlimited)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("KAFKA CONSOLE PRODUCER - Test Scenario Generator")
    print("=" * 70)
    
    # Pre-flight checks
    if not check_container_running():
        print(f"\nError: Container '{CONTAINER_NAME}' is not running")
        print("Run: docker compose up -d kafka-broker1")
        return 1
    
    if not SCENARIOS_DIR.exists():
        print(f"\nError: Scenarios directory not found: {SCENARIOS_DIR}")
        return 1
    
    # Determine which scenarios to produce
    if args.scenario == 'all':
        scenario_files = sorted(SCENARIOS_DIR.glob('scenario_*.jsonl'))
        if not scenario_files:
            print(f"\nError: No scenario files found in {SCENARIOS_DIR}")
            return 1
    else:
        # Handle with or without .jsonl extension
        scenario_name = args.scenario if args.scenario.endswith('.jsonl') else f"{args.scenario}.jsonl"
        scenario_path = SCENARIOS_DIR / scenario_name
        
        if not scenario_path.exists():
            print(f"\nError: Scenario file not found: {scenario_path}")
            print(f"\nAvailable scenarios:")
            for f in sorted(SCENARIOS_DIR.glob('scenario_*.jsonl')):
                print(f"  - {f.stem}")
            return 1
        
        scenario_files = [scenario_path]
    
    print(f"\nScenarios to produce: {len(scenario_files)}")
    print(f"Target topic: {args.topic}")
    print(f"Target rate: {args.rate} msg/sec")
    print(f"Max events per scenario: {args.max or 'unlimited'}")
    
    # Produce each scenario
    total_sent = 0
    total_failed = 0
    
    try:
        for scenario_file in scenario_files:
            sent, failed = produce_scenario_file(
                scenario_file,
                args.topic,
                args.rate,
                args.max
            )
            total_sent += sent
            total_failed += failed
        
        # Overall summary
        print(f"\n{'='*70}")
        print("OVERALL SUMMARY")
        print(f"{'='*70}")
        print(f"Total scenarios:  {len(scenario_files)}")
        print(f"Total sent:       {total_sent}")
        print(f"Total failed:     {total_failed}")
        print(f"Success rate:     {total_sent/(total_sent+total_failed)*100:.1f}%")
        print(f"{'='*70}")
        
        if total_failed > 0:
            print(f"\nWarning: {total_failed} events failed to send")
            return 1
        else:
            print(f"\nSuccess! All {total_sent} events produced successfully")
            return 0
            
    except KeyboardInterrupt:
        print(f"\n\nInterrupted by user")
        print(f"Produced {total_sent} events before interruption")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
