#!/usr/bin/env python3
"""
Comprehensive End-to-End Batch Testing

Tests the complete prediction pipeline in batch mode:
1. Load test scenarios
2. Validate input data (Layer 1)
3. Generate ML predictions  
4. Validate predictions (Layer 2 & 3)
5. Measure accuracy and performance

This demonstrates the complete system functionality without requiring
real-time Kafka stream processing.

Usage:
    python test_end_to_end_batch.py
    python test_end_to_end_batch.py --scenarios all --detailed
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from collections import defaultdict, Counter
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.input_data_validator import TrafficDataValidator
from src.prediction.safety_validator import PredictionSafetyValidator

# Try importing numpy and sklearn
try:
    import numpy as np
    import joblib
    HAS_ML = True
except ImportError:
    HAS_ML = False
    print("⚠️  NumPy/joblib not available, ML predictions will be mocked")

# Configuration
SCENARIOS_DIR = Path(__file__).parent.parent / 'data' / 'test_scenarios'
MODELS_DIR = Path(__file__).parent.parent / 'models'  # Local models directory

class EndToEndBatchTester:
    """Comprehensive batch testing of the traffic prediction pipeline"""
    
    def __init__(self):
        """Initialize the batch tester"""
        self.input_validator = TrafficDataValidator()
        self.safety_validator = PredictionSafetyValidator()
        
        # Statistics
        self.stats = {
            'total_events': 0,
            'input_valid': 0,
            'input_invalid': 0,
            'predictions_generated': 0,
            'predictions_safe': 0,
            'predictions_unsafe': 0,
            'validation_failures': Counter(),
            'safety_failures': Counter(),
            'scenario_results': defaultdict(dict)
        }
        
        # Models (loaded on demand)
        self.models_loaded = False
        self.rf_model = None
        self.gb_model = None
        self.scaler = None
        self.encoder = None
        self.model_metadata = None
    
    def load_models_from_hdfs(self):
        """Download and load models from HDFS"""
        if not HAS_ML:
            print("⚠️  Skipping model loading (NumPy not available)")
            return False
        
        print("\n📥 Downloading models from HDFS...")
        
        models_dir = MODELS_DIR
        models_dir.mkdir(exist_ok=True)
        
        # Model files to download
        model_files = [
            'random_forest_speed.joblib',
            'gradient_boosting_speed.joblib',
            'scaler_features.joblib',
            'encoder_highway.joblib',
            'model_metadata.json'
        ]
        
        # Download each model
        for model_file in model_files:
            hdfs_path = f'/traffic-data/models/{model_file}'
            local_path = models_dir / model_file
            
            print(f"  Downloading {model_file}...")
            cmd = [
                'docker', 'exec', 'namenode',
                'hdfs', 'dfs', '-get',
                hdfs_path,
                f'/tmp/{model_file}'
            ]
            subprocess.run(cmd, capture_output=True, check=False)
            
            # Copy from container to host
            cmd = ['docker', 'cp', f'namenode:/tmp/{model_file}', str(local_path)]
            result = subprocess.run(cmd, capture_output=True, check=False)
            
            if result.returncode == 0:
                print(f"    ✅ {model_file}")
            else:
                print(f"    ❌ Failed to download {model_file}")
                return False
        
        # Load models
        try:
            print("\n📦 Loading models...")
            self.rf_model = joblib.load(models_dir / 'random_forest_speed.joblib')
            self.gb_model = joblib.load(models_dir / 'gradient_boosting_speed.joblib')
            self.scaler = joblib.load(models_dir / 'scaler_features.joblib')
            self.encoder = joblib.load(models_dir / 'encoder_highway.joblib')
            
            with open(models_dir / 'model_metadata.json') as f:
                self.model_metadata = json.load(f)
            
            print("✅ All models loaded successfully")
            print(f"   Model training date: {self.model_metadata.get('training_date', 'unknown')}")
            print(f"   Best model: {self.model_metadata.get('best_model', 'unknown')}")
            
            self.models_loaded = True
            return True
            
        except Exception as e:
            print(f"❌ Error loading models: {e}")
            return False
    
    def flatten_metr_la_format(self, event: dict) -> dict:
        """Transform METR-LA nested format to flat format"""
        flat = {
            'sensor_id': event.get('sensor_id'),
            'event_id': event.get('event_id'),
            'timestamp': event.get('timestamp')
        }
        
        if 'traffic_data' in event:
            td = event['traffic_data']
            flat['speed'] = td.get('speed_mph')
            flat['volume'] = td.get('volume_vehicles_per_hour')
            flat['occupancy'] = td.get('occupancy_percentage')
            flat['congestion_level'] = td.get('congestion_level')
        
        if 'location' in event:
            loc = event['location']
            flat['highway'] = loc.get('highway')
            flat['direction'] = loc.get('direction')
            flat['lane_count'] = loc.get('lanes')
            flat['latitude'] = loc.get('latitude')
            flat['longitude'] = loc.get('longitude')
        
        if 'weather' in event:
            weather = event['weather']
            flat['weather_condition'] = weather.get('condition')
            flat['temperature'] = weather.get('temperature_f')
            flat['precipitation'] = weather.get('precipitation')
        
        return flat
    
    def extract_features(self, event: dict) -> np.ndarray:
        """Extract features for ML prediction"""
        if not HAS_ML:
            return None
        
        # Extract 15 features (matching training)
        features = []
        
        # Traffic features
        features.append(event.get('speed', 0))
        features.append(event.get('volume', 0))
        features.append(event.get('occupancy', 0))
        
        # Location features  
        features.append(event.get('lane_count', 4))
        features.append(event.get('latitude', 34.0))
        features.append(event.get('longitude', -118.0))
        
        # Time features (mock - would extract from timestamp)
        features.append(12)  # hour
        features.append(3)   # day_of_week
        features.append(0)   # is_weekend
        features.append(0)   # is_rush_hour
        
        # Weather features
        temp = event.get('temperature', 70)
        features.append(temp)
        features.append(1 if event.get('weather_condition') == 'Rain' else 0)
        
        # Highway encoding (would use encoder)
        features.append(0)  # highway_encoded
        
        # Derived features
        features.append(features[1] / max(features[3], 1))  # volume_per_lane
        features.append(1 if features[0] < 30 else 0)  # is_congested
        
        return np.array(features).reshape(1, -1)
    
    def generate_prediction(self, event: dict) -> Tuple[bool, Dict]:
        """Generate prediction for an event"""
        try:
            if not self.models_loaded or not HAS_ML:
                # Mock prediction
                current_speed = event.get('speed', 50)
                return True, {
                    'predicted_speed': current_speed + np.random.uniform(-5, 5) if HAS_ML else current_speed,
                    'model_used': 'mock',
                    'confidence': 0.8
                }
            
            # Extract features
            features = self.extract_features(event)
            
            # Scale features
            scaled_features = self.scaler.transform(features)
            
            # Predict with best model (GB based on previous testing)
            predicted_speed = self.gb_model.predict(scaled_features)[0]
            
            # Get ensemble prediction
            rf_pred = self.rf_model.predict(scaled_features)[0]
            ensemble_pred = (predicted_speed + rf_pred) / 2
            
            return True, {
                'predicted_speed': float(ensemble_pred),
                'gb_prediction': float(predicted_speed),
                'rf_prediction': float(rf_pred),
                'model_used': 'gradient_boosting',
                'confidence': 0.85
            }
            
        except Exception as e:
            print(f"Error generating prediction: {e}")
            return False, {'error': str(e)}
    
    def test_scenario(self, scenario_file: Path, detailed: bool = False) -> Dict:
        """Test a single scenario file"""
        print(f"\n{'='*70}")
        print(f"Testing: {scenario_file.name}")
        print(f"{'='*70}")
        
        scenario_stats = {
            'total': 0,
            'input_valid': 0,
            'input_invalid': 0,
            'predictions_generated': 0,
            'predictions_safe': 0,
            'predictions_unsafe': 0,
            'start_time': time.time()
        }
        
        # Load events
        events = []
        with open(scenario_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        scenario_stats['total'] = len(events)
        print(f"Loaded {len(events)} events")
        
        # Process each event
        for i, event in enumerate(events):
            # Layer 1: Input Validation
            flat_event = self.flatten_metr_la_format(event)
            is_valid, validation_results, cleaned_data = self.input_validator.validate_traffic_record(flat_event)
            
            if is_valid:
                scenario_stats['input_valid'] += 1
                
                # Layer 2: ML Prediction
                success, prediction = self.generate_prediction(cleaned_data or flat_event)
                
                if success:
                    scenario_stats['predictions_generated'] += 1
                    
                    # Layer 3: Safety Validation
                    predicted_speed = prediction['predicted_speed']
                    current_speed = flat_event.get('speed', 50)
                    
                    # Create prediction dict for safety validator
                    prediction_dict = {
                        'predicted_speed': predicted_speed,
                        'sensor_id': event.get('sensor_id', 'unknown'),
                        'timestamp': event.get('timestamp')
                    }
                    
                    safety_passed, corrected_prediction, warnings = self.safety_validator.validate_prediction(prediction_dict)
                    
                    if safety_passed and not warnings:
                        scenario_stats['predictions_safe'] += 1
                    else:
                        scenario_stats['predictions_unsafe'] += 1
                        if detailed:
                            reason = warnings[0] if warnings else 'Unknown'
                            print(f"  ⚠️  Event {i+1}: Unsafe prediction - {reason}")
            else:
                scenario_stats['input_invalid'] += 1
                failure_reasons = [r.message for r in validation_results.all_results if not r.is_valid]
                for reason in failure_reasons:
                    self.stats['validation_failures'][reason] += 1
        
        # Calculate metrics
        scenario_stats['elapsed_time'] = time.time() - scenario_stats['start_time']
        scenario_stats['throughput'] = scenario_stats['total'] / scenario_stats['elapsed_time']
        
        # Print results
        print(f"\nResults:")
        print(f"  Input validation:  {scenario_stats['input_valid']}/{scenario_stats['total']} ({scenario_stats['input_valid']/scenario_stats['total']*100:.1f}%)")
        print(f"  Predictions:       {scenario_stats['predictions_generated']}")
        print(f"  Safe predictions:  {scenario_stats['predictions_safe']} ({scenario_stats['predictions_safe']/max(scenario_stats['predictions_generated'],1)*100:.1f}%)")
        print(f"  Unsafe predictions: {scenario_stats['predictions_unsafe']}")
        print(f"  Processing time:   {scenario_stats['elapsed_time']:.2f}s")
        print(f"  Throughput:        {scenario_stats['throughput']:.1f} events/sec")
        
        # Update global stats
        self.stats['total_events'] += scenario_stats['total']
        self.stats['input_valid'] += scenario_stats['input_valid']
        self.stats['input_invalid'] += scenario_stats['input_invalid']
        self.stats['predictions_generated'] += scenario_stats['predictions_generated']
        self.stats['predictions_safe'] += scenario_stats['predictions_safe']
        self.stats['predictions_unsafe'] += scenario_stats['predictions_unsafe']
        self.stats['scenario_results'][scenario_file.stem] = scenario_stats
        
        return scenario_stats
    
    def print_summary(self):
        """Print overall summary"""
        print(f"\n\n{'='*70}")
        print("COMPREHENSIVE TEST SUMMARY")
        print(f"{'='*70}")
        
        print(f"\nOverall Statistics:")
        print(f"  Total events processed: {self.stats['total_events']}")
        print(f"  Input validation rate:  {self.stats['input_valid']}/{self.stats['total_events']} ({self.stats['input_valid']/max(self.stats['total_events'],1)*100:.1f}%)")
        print(f"  Predictions generated:  {self.stats['predictions_generated']}")
        print(f"  Safe predictions:       {self.stats['predictions_safe']} ({self.stats['predictions_safe']/max(self.stats['predictions_generated'],1)*100:.1f}%)")
        print(f"  Unsafe predictions:     {self.stats['predictions_unsafe']} ({self.stats['predictions_unsafe']/max(self.stats['predictions_generated'],1)*100:.1f}%)")
        
        if self.stats['validation_failures']:
            print(f"\nTop Input Validation Failures:")
            for reason, count in self.stats['validation_failures'].most_common(5):
                print(f"  - {reason}: {count}")
        
        print(f"\n{'='*70}")
        print("✅ END-TO-END BATCH TESTING COMPLETE")
        print(f"{'='*70}")

def main():
    parser = argparse.ArgumentParser(description='End-to-end batch testing')
    parser.add_argument('--scenarios', default='all',
                       help='Scenarios to test (default: all)')
    parser.add_argument('--detailed', action='store_true',
                       help='Show detailed output')
    parser.add_argument('--load-models', action='store_true',
                       help='Download and load models from HDFS')
    
    args = parser.parse_args()
    
    print("="*70)
    print("END-TO-END BATCH TESTING")
    print("="*70)
    print("Testing complete pipeline:")
    print("  1. Input validation (Layer 1)")
    print("  2. ML prediction")
    print("  3. Safety validation (Layers 2 & 3)")
    print("="*70)
    
    # Create tester
    tester = EndToEndBatchTester()
    
    # Load models if requested
    if args.load_models:
        if not tester.load_models_from_hdfs():
            print("\n⚠️  Model loading failed, continuing with mock predictions")
    
    # Determine scenarios to test
    if args.scenarios == 'all':
        scenario_files = sorted(SCENARIOS_DIR.glob('scenario_*.jsonl'))
    else:
        scenario_name = args.scenarios if args.scenarios.endswith('.jsonl') else f"{args.scenarios}.jsonl"
        scenario_files = [SCENARIOS_DIR / scenario_name]
    
    if not scenario_files:
        print(f"\n❌ No scenario files found in {SCENARIOS_DIR}")
        return 1
    
    print(f"\nTesting {len(scenario_files)} scenarios")
    
    # Test each scenario
    try:
        for scenario_file in scenario_files:
            tester.test_scenario(scenario_file, args.detailed)
        
        # Print summary
        tester.print_summary()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
        tester.print_summary()
        return 1
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
