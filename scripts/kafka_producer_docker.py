#!/usr/bin/env python3
"""
Docker-based Kafka Producer for Test Scenarios

Runs the Kafka producer inside the kafka-broker1 container to avoid
host-to-container networking issues with advertised listeners.

This wrapper script:
1. Copies scenario files into the container
2. Installs kafka-python if needed
3. Runs the producer from inside the container
4. Streams output back to the host

Usage:
    python kafka_producer_docker.py --scenario all --rate 10
    python kafka_producer_docker.py --scenario scenario_1_normal_traffic --rate 100
"""

import argparse
import subprocess
import sys
from pathlib import Path

CONTAINER_NAME = 'kafka-broker1'
SCENARIOS_DIR = Path(__file__).parent.parent / 'data' / 'test_scenarios'

def run_command(cmd: list, check=True, capture=False):
    """Run a command and optionally capture output"""
    print(f"🔧 Running: {' '.join(cmd)}")
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd, check=check)
        return result.returncode == 0

def check_container_running():
    """Verify kafka-broker1 container is running"""
    result = subprocess.run(
        ['docker', 'ps', '--filter', f'name={CONTAINER_NAME}', '--format', '{{.Names}}'],
        capture_output=True,
        text=True
    )
    return CONTAINER_NAME in result.stdout

def copy_files_to_container():
    """Copy scenario files into container"""
    print(f"\n📦 Copying scenario files to container...")
    
    # Create directory in container
    run_command(['docker', 'exec', CONTAINER_NAME, 'mkdir', '-p', '/tmp/test_scenarios'])
    
    # Copy each scenario file
    scenario_files = list(SCENARIOS_DIR.glob('*.jsonl'))
    for file in scenario_files:
        print(f"  📄 {file.name}")
        run_command(['docker', 'cp', str(file), f'{CONTAINER_NAME}:/tmp/test_scenarios/'])
    
    print(f"✅ Copied {len(scenario_files)} scenario files")
    return len(scenario_files)

def install_kafka_python():
    """Install kafka-python in container if not already installed"""
    print(f"\n📦 Checking kafka-python installation...")
    
    # Check if already installed
    check_cmd = ['docker', 'exec', CONTAINER_NAME, 'python3', '-c', 
                 'import kafka; print("installed")']
    try:
        result = subprocess.run(check_cmd, capture_output=True, text=True, check=False)
        if 'installed' in result.stdout:
            print("✅ kafka-python already installed")
            return True
    except:
        pass
    
    # Install kafka-python
    print("📥 Installing kafka-python (this may take a minute)...")
    install_cmd = ['docker', 'exec', CONTAINER_NAME, 'pip', 'install', 
                   'kafka-python==2.0.2', '--quiet']
    success = run_command(install_cmd, check=False)
    
    if success:
        print("✅ kafka-python installed successfully")
    else:
        print("⚠️  Installation may have warnings but continuing...")
    
    return True

def create_producer_script():
    """Create the producer script inside the container"""
    script_content = '''#!/usr/bin/env python3
import json
import time
import sys
from pathlib import Path
from kafka import KafkaProducer
from kafka.errors import KafkaError

def produce_scenario(file_path, topic, rate_limit, max_events=None):
    """Produce events from a scenario file"""
    
    # Initialize producer (using internal listener)
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],  # Internal port
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3,
        max_in_flight_requests_per_connection=1
    )
    
    delay = 1.0 / rate_limit if rate_limit > 0 else 0
    
    sent = 0
    failed = 0
    
    print(f"📤 Producing from {Path(file_path).name}")
    print(f"   Topic: {topic}, Rate: {rate_limit} msg/sec")
    
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if max_events and sent >= max_events:
                    break
                
                try:
                    event = json.loads(line.strip())
                    sensor_id = event.get('sensor_id', 'default')
                    
                    future = producer.send(topic, value=event, key=sensor_id)
                    future.get(timeout=10)
                    
                    sent += 1
                    if sent % 100 == 0:
                        print(f"  ✅ Sent {sent} messages...")
                    
                    if delay > 0:
                        time.sleep(delay)
                        
                except Exception as e:
                    failed += 1
                    if failed <= 5:
                        print(f"  ❌ Error on line {line_num}: {e}")
                    
        producer.flush()
        
    finally:
        producer.close()
    
    print(f"\\n📊 Results:")
    print(f"   Sent: {sent}")
    print(f"   Failed: {failed}")
    print(f"   Success rate: {sent/(sent+failed)*100:.1f}%")
    
    return sent, failed

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--topic', default='traffic-raw')
    parser.add_argument('--rate', type=float, default=10.0)
    parser.add_argument('--max', type=int, default=None)
    args = parser.parse_args()
    
    sent, failed = produce_scenario(args.file, args.topic, args.rate, args.max)
    sys.exit(0 if failed == 0 else 1)
'''
    
    print("\n📝 Creating producer script in container...")
    
    # Write script to temp file (with UTF-8 encoding for Windows)
    script_path = Path(__file__).parent / 'temp_producer.py'
    script_path.write_text(script_content, encoding='utf-8')
    
    # Copy to container
    run_command(['docker', 'cp', str(script_path), f'{CONTAINER_NAME}:/tmp/producer.py'])
    
    # Make executable
    run_command(['docker', 'exec', CONTAINER_NAME, 'chmod', '+x', '/tmp/producer.py'])
    
    # Clean up temp file
    script_path.unlink()
    
    print("✅ Producer script ready")

def produce_scenario(scenario_name, topic, rate, max_events):
    """Run the producer for a specific scenario"""
    
    if scenario_name == 'all':
        scenario_files = [f'/tmp/test_scenarios/{f}' for f in 
                         ['scenario_1_normal_traffic.jsonl',
                          'scenario_2_morning_rush.jsonl',
                          'scenario_3_evening_rush.jsonl',
                          'scenario_4_accident.jsonl',
                          'scenario_5_weather_impact.jsonl']]
    else:
        scenario_files = [f'/tmp/test_scenarios/{scenario_name}.jsonl']
    
    print(f"\n🚀 Starting production...")
    print(f"   Scenarios: {len(scenario_files)}")
    print(f"   Topic: {topic}")
    print(f"   Rate: {rate} msg/sec")
    
    total_sent = 0
    total_failed = 0
    
    for file_path in scenario_files:
        cmd = ['docker', 'exec', CONTAINER_NAME, 'python3', '/tmp/producer.py',
               '--file', file_path,
               '--topic', topic,
               '--rate', str(rate)]
        
        if max_events:
            cmd.extend(['--max', str(max_events)])
        
        print(f"\n{'='*60}")
        result = subprocess.run(cmd)
        print(f"{'='*60}")
        
        if result.returncode != 0:
            print(f"⚠️  Production failed for {file_path}")
    
    print(f"\n✅ Production complete!")

def main():
    parser = argparse.ArgumentParser(description='Produce test scenarios to Kafka from Docker container')
    parser.add_argument('--scenario', default='all',
                       help='Scenario to produce (default: all)')
    parser.add_argument('--topic', default='traffic-raw',
                       help='Kafka topic (default: traffic-raw)')
    parser.add_argument('--rate', type=float, default=10.0,
                       help='Messages per second (default: 10)')
    parser.add_argument('--max', type=int, default=None,
                       help='Maximum messages per scenario (default: unlimited)')
    
    args = parser.parse_args()
    
    print("🐳 Docker-based Kafka Producer")
    print("="*60)
    
    # Pre-flight checks
    if not check_container_running():
        print(f"❌ Error: Container '{CONTAINER_NAME}' is not running")
        print("   Run: docker compose up -d kafka-broker1")
        return 1
    
    if not SCENARIOS_DIR.exists():
        print(f"❌ Error: Scenarios directory not found: {SCENARIOS_DIR}")
        return 1
    
    # Setup
    try:
        copy_files_to_container()
        install_kafka_python()
        create_producer_script()
        
        # Produce
        produce_scenario(args.scenario, args.topic, args.rate, args.max)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
