"""
Complete METR-LA Traffic Prediction Workflow Orchestrator
Orchestrates the full pipeline: CSV → Kafka → Spark Streaming → HDFS → ML → Predictions → Dashboard
"""

import os
import sys
import time
import logging
import subprocess
import threading
import signal
from pathlib import Path
from typing import List, Dict, Any
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrafficPipelineOrchestrator:
    """Orchestrates the complete traffic prediction pipeline"""
    
    def __init__(self):
        self.processes = {}
        self.running = True
        self.setup_signal_handlers()
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal. Stopping all processes...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        logger.info("Checking prerequisites...")
        
        prerequisites = {
            'docker': 'docker --version',
            'python': 'python --version',
            'java': 'java -version',
            # 'kafka': 'docker exec kafka-broker1 kafka-topics --list --bootstrap-server localhost:9092',
            # 'hdfs': 'docker exec namenode hdfs dfs -ls /'
        }
        
        for name, cmd in prerequisites.items():
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"✓ {name} is available")
                else:
                    logger.error(f"✗ {name} check failed: {result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"✗ Error checking {name}: {e}")
                return False
        
        return True
    
    def check_docker_services(self) -> bool:
        """Check if required Docker services are running"""
        logger.info("Checking Docker services...")
        
        required_services = [
            'zookeeper', 'kafka-broker1', 'namenode', 'datanode'
        ]
        
        try:
            result = subprocess.run(
                'docker ps --format "{{.Names}}"', 
                shell=True, capture_output=True, text=True
            )
            
            if result.returncode != 0:
                logger.error("Failed to get Docker container list")
                return False
            
            running_services = result.stdout.strip().split('\n')
            
            missing_services = []
            for service in required_services:
                if service not in running_services:
                    missing_services.append(service)
            
            if missing_services:
                logger.error(f"Missing Docker services: {missing_services}")
                logger.info("Please start the services using: docker-compose up -d")
                return False
            
            logger.info("✓ All required Docker services are running")
            return True
            
        except Exception as e:
            logger.error(f"Error checking Docker services: {e}")
            return False
    
    def create_kafka_topics(self) -> bool:
        """Create required Kafka topics"""
        logger.info("Creating Kafka topics...")
        
        topics = [
            'traffic-events',
            'traffic-predictions'
        ]
        
        for topic in topics:
            try:
                cmd = f'''docker exec kafka-broker1 kafka-topics --create \
                    --topic {topic} \
                    --bootstrap-server localhost:9092 \
                    --partitions 3 \
                    --replication-factor 1 \
                    --if-not-exists'''
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"✓ Topic '{topic}' created/verified")
                else:
                    logger.warning(f"Topic creation result for '{topic}': {result.stderr}")
                    
            except Exception as e:
                logger.error(f"Error creating topic '{topic}': {e}")
                return False
        
        return True
    
    def setup_hdfs_directories(self) -> bool:
        """Setup HDFS directory structure"""
        logger.info("Setting up HDFS directories...")
        
        directories = [
            '/traffic-data',
            '/traffic-data/streaming',
            '/traffic-data/streaming/raw-events',
            '/traffic-data/streaming/sensor-aggregates',
            '/traffic-data/streaming/road-aggregates',
            '/traffic-data/models',
            '/traffic-data/predictions'
        ]
        
        for directory in directories:
            try:
                cmd = f'docker exec namenode hdfs dfs -mkdir -p {directory}'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"✓ HDFS directory '{directory}' created")
                else:
                    # Directory might already exist
                    logger.debug(f"HDFS directory result for '{directory}': {result.stderr}")
                    
            except Exception as e:
                logger.error(f"Error creating HDFS directory '{directory}': {e}")
                return False
        
        return True
    
    def start_kafka_producer(self, csv_file: str, replay_speed: float = 10.0) -> bool:
        """Start the Kafka producer for METR-LA data"""
        logger.info(f"Starting Kafka producer with replay speed {replay_speed}x...")
        
        cmd = [
            'python', 'scripts/metr_la_kafka_producer.py',
            '--csv-file', csv_file,
            '--kafka-broker', 'localhost:9093',
            '--topic', 'traffic-events',
            '--replay-speed', str(replay_speed)
        ]
        
        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes['kafka_producer'] = process
            logger.info("✓ Kafka producer started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting Kafka producer: {e}")
            return False
    
    def start_spark_streaming(self) -> bool:
        """Start Spark Structured Streaming processor"""
        logger.info("Starting Spark Structured Streaming...")
        
        cmd = ['python', 'scripts/spark_streaming_processor.py']
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes['spark_streaming'] = process
            logger.info("✓ Spark Structured Streaming started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting Spark Streaming: {e}")
            return False
    
    def wait_for_data_accumulation(self, wait_minutes: int = 5) -> bool:
        """Wait for data to accumulate before training"""
        logger.info(f"Waiting {wait_minutes} minutes for data accumulation...")
        
        for i in range(wait_minutes):
            if not self.running:
                return False
            
            logger.info(f"Waiting... {i+1}/{wait_minutes} minutes")
            time.sleep(60)
            
            # Check if we have data in HDFS
            try:
                cmd = 'docker exec namenode hdfs dfs -ls /traffic-data/streaming/sensor-aggregates'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0 and 'parquet' in result.stdout:
                    logger.info("✓ Data detected in HDFS, proceeding...")
                    return True
                    
            except Exception as e:
                logger.debug(f"Checking HDFS data: {e}")
        
        logger.info("✓ Data accumulation period completed")
        return True
    
    def train_ml_models(self) -> bool:
        """Train ML models from HDFS data"""
        logger.info("Training ML models...")
        
        cmd = ['python', 'scripts/ml_training_pipeline.py']
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )
            
            if result.returncode == 0:
                logger.info("✓ ML model training completed successfully")
                logger.info("Training output:\n" + result.stdout[-500:])  # Last 500 chars
                return True
            else:
                logger.error(f"ML training failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("ML training timed out after 30 minutes")
            return False
        except Exception as e:
            logger.error(f"Error in ML training: {e}")
            return False
    
    def start_prediction_service(self, continuous: bool = True) -> bool:
        """Start the prediction service"""
        logger.info("Starting prediction service...")
        
        cmd = ['python', 'scripts/prediction_service.py']
        if continuous:
            cmd.extend(['--continuous', '--interval', '2'])
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes['prediction_service'] = process
            logger.info("✓ Prediction service started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting prediction service: {e}")
            return False
    
    def start_dashboard(self) -> bool:
        """Start the Next.js dashboard"""
        logger.info("Starting Next.js dashboard...")
        
        cmd = ['npm', 'run', 'dev']
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes['dashboard'] = process
            logger.info("✓ Dashboard started at http://localhost:3000")
            return True
            
        except Exception as e:
            logger.error(f"Error starting dashboard: {e}")
            return False
    
    def monitor_processes(self):
        """Monitor running processes and log their output"""
        logger.info("Starting process monitoring...")
        
        def monitor_process(name, process):
            while self.running and process.poll() is None:
                try:
                    output = process.stdout.readline()
                    if output:
                        logger.info(f"[{name}] {output.strip()}")
                    time.sleep(0.1)
                except:
                    break
        
        # Start monitoring threads for each process
        for name, process in self.processes.items():
            if process and process.poll() is None:
                thread = threading.Thread(
                    target=monitor_process, 
                    args=(name, process),
                    daemon=True
                )
                thread.start()
    
    def cleanup(self):
        """Cleanup all running processes"""
        logger.info("Cleaning up processes...")
        
        for name, process in self.processes.items():
            if process and process.poll() is None:
                logger.info(f"Terminating {name}...")
                try:
                    process.terminate()
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing {name}...")
                    process.kill()
                except Exception as e:
                    logger.error(f"Error terminating {name}: {e}")
    
    def run_full_pipeline(self, csv_file: str, replay_speed: float = 10.0):
        """Run the complete pipeline"""
        logger.info("="*50)
        logger.info("STARTING COMPLETE METR-LA TRAFFIC PREDICTION PIPELINE")
        logger.info("="*50)
        
        try:
            # Step 1: Prerequisites
            if not self.check_prerequisites():
                logger.error("Prerequisites check failed")
                return False
            
            # Step 2: Docker services
            if not self.check_docker_services():
                logger.error("Docker services check failed")
                return False
            
            # Step 3: Create Kafka topics
            if not self.create_kafka_topics():
                logger.error("Kafka topics creation failed")
                return False
            
            # Step 4: Setup HDFS directories
            if not self.setup_hdfs_directories():
                logger.error("HDFS setup failed")
                return False
            
            # Step 5: Start Kafka producer
            if not self.start_kafka_producer(csv_file, replay_speed):
                logger.error("Kafka producer startup failed")
                return False
            
            # Step 6: Start Spark Streaming
            if not self.start_spark_streaming():
                logger.error("Spark Streaming startup failed")
                return False
            
            # Step 7: Wait for data accumulation
            if not self.wait_for_data_accumulation(3):  # 3 minutes
                logger.error("Data accumulation failed")
                return False
            
            # Step 8: Train ML models
            if not self.train_ml_models():
                logger.error("ML training failed")
                return False
            
            # Step 9: Start prediction service
            if not self.start_prediction_service():
                logger.error("Prediction service startup failed")
                return False
            
            # Step 10: Start dashboard
            if not self.start_dashboard():
                logger.error("Dashboard startup failed")
                return False
            
            # Step 11: Monitor everything
            self.monitor_processes()
            
            logger.info("="*50)
            logger.info("PIPELINE FULLY OPERATIONAL!")
            logger.info("="*50)
            logger.info("Dashboard: http://localhost:3000/dashboard")
            logger.info("Kafka UI: http://localhost:8080")
            logger.info("HDFS UI: http://localhost:9870")
            logger.info("Press Ctrl+C to stop all services")
            
            # Keep running until interrupted
            while self.running:
                time.sleep(1)
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            return False
        finally:
            self.cleanup()
    
    def run_quick_demo(self, csv_file: str):
        """Run a quick demo with faster processing"""
        logger.info("Running quick demo mode...")
        self.run_full_pipeline(csv_file, replay_speed=50.0)  # 50x speed

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='METR-LA Traffic Prediction Pipeline Orchestrator')
    parser.add_argument('--csv-file', required=True, help='Path to METR-LA CSV file')
    parser.add_argument('--replay-speed', type=float, default=10.0, 
                       help='Data replay speed multiplier (default: 10x)')
    parser.add_argument('--quick-demo', action='store_true', 
                       help='Run quick demo with 50x speed')
    
    args = parser.parse_args()
    
    # Validate CSV file exists
    if not Path(args.csv_file).exists():
        logger.error(f"CSV file not found: {args.csv_file}")
        sys.exit(1)
    
    # Create orchestrator and run
    orchestrator = TrafficPipelineOrchestrator()
    
    if args.quick_demo:
        orchestrator.run_quick_demo(args.csv_file)
    else:
        orchestrator.run_full_pipeline(args.csv_file, args.replay_speed)

if __name__ == "__main__":
    main()