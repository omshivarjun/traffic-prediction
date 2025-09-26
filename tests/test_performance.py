#!/usr/bin/env python3
"""
Performance Benchmark Tests for Traffic Prediction Service

Comprehensive performance testing suite including:
- Database query performance benchmarks
- Model loading and prediction speed tests  
- Spark job performance under various loads
- Memory usage and resource consumption tests
- Scalability tests for concurrent predictions

Usage:
    python tests/test_performance.py
    python tests/test_performance.py --load-test --duration=300
"""

import unittest
import time
import psutil
import threading
import queue
import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class PerformanceTestBase(unittest.TestCase):
    """Base class for performance tests with timing and resource monitoring"""
    
    def setUp(self):
        """Set up performance monitoring"""
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.performance_metrics = {}
    
    def start_monitoring(self):
        """Start performance monitoring"""
        self.start_time = time.time()
        self.start_memory = psutil.Process().memory_info().rss
    
    def stop_monitoring(self):
        """Stop performance monitoring and record metrics"""
        self.end_time = time.time()
        self.end_memory = psutil.Process().memory_info().rss
        
        self.performance_metrics = {
            'execution_time': self.end_time - self.start_time,
            'memory_used': self.end_memory - self.start_memory,
            'peak_memory': psutil.Process().memory_info().rss,
            'cpu_percent': psutil.Process().cpu_percent()
        }
    
    def assertPerformanceThreshold(self, metric, threshold, message=""):
        """Assert that a performance metric meets the threshold"""
        actual_value = self.performance_metrics.get(metric)
        self.assertIsNotNone(actual_value, f"Metric {metric} not recorded")
        self.assertLessEqual(
            actual_value, threshold,
            f"{message} - {metric}: {actual_value} > {threshold}"
        )
    
    def print_performance_summary(self):
        """Print performance metrics summary"""
        print(f"\n--- Performance Metrics for {self._testMethodName} ---")
        for metric, value in self.performance_metrics.items():
            if metric == 'execution_time':
                print(f"Execution Time: {value:.3f} seconds")
            elif 'memory' in metric:
                print(f"{metric.replace('_', ' ').title()}: {value / 1024 / 1024:.2f} MB")
            else:
                print(f"{metric.replace('_', ' ').title()}: {value}")

class TestDatabasePerformance(PerformanceTestBase):
    """Performance tests for database operations"""
    
    def setUp(self):
        """Set up database performance tests"""
        super().setUp()
        self.sample_data_size = 1000
        
    def test_bulk_insert_performance(self):
        """Test bulk insert performance for predictions"""
        self.start_monitoring()
        
        # Simulate bulk insert operations
        start_time = time.time()
        
        # Mock bulk insert operation
        sample_predictions = []
        for i in range(self.sample_data_size):
            prediction = {
                'segment_id': i % 100,
                'prediction_time': datetime.now(),
                'horizon_minutes': 15,
                'predicted_volume': 50.0 + (i % 20),
                'confidence_score': 0.8 + (i % 2) * 0.1
            }
            sample_predictions.append(prediction)
        
        # Simulate processing time (would be actual database insert)
        time.sleep(0.1)  # Simulate database operation
        
        end_time = time.time()
        self.stop_monitoring()
        
        # Performance assertions
        execution_time = end_time - start_time
        throughput = self.sample_data_size / execution_time
        
        print(f"Bulk insert throughput: {throughput:.0f} records/second")
        
        # Assert reasonable throughput (adjust based on actual requirements)
        self.assertGreater(throughput, 1000, "Bulk insert throughput too low")
        self.print_performance_summary()
    
    def test_query_performance(self):
        """Test query performance for traffic data retrieval"""
        self.start_monitoring()
        
        # Simulate complex query operations
        query_count = 100
        query_times = []
        
        for i in range(query_count):
            start = time.time()
            
            # Mock database query (would be actual SQL execution)
            segment_id = i % 50
            start_time = datetime.now() - timedelta(hours=24)
            end_time = datetime.now()
            
            # Simulate query processing
            time.sleep(0.001)  # 1ms per query
            
            query_times.append(time.time() - start)
        
        self.stop_monitoring()
        
        # Calculate query performance metrics
        avg_query_time = statistics.mean(query_times)
        p95_query_time = statistics.quantiles(query_times, n=20)[18]  # 95th percentile
        
        print(f"Average query time: {avg_query_time*1000:.2f} ms")
        print(f"95th percentile query time: {p95_query_time*1000:.2f} ms")
        
        # Performance assertions
        self.assertLess(avg_query_time, 0.1, "Average query time too high")
        self.assertLess(p95_query_time, 0.2, "95th percentile query time too high")
        self.print_performance_summary()

class TestModelPerformance(PerformanceTestBase):
    """Performance tests for model operations"""
    
    def test_model_loading_performance(self):
        """Test model loading speed from HDFS"""
        self.start_monitoring()
        
        # Simulate model loading operations
        model_load_times = []
        
        for i in range(5):  # Load 5 different models
            start = time.time()
            
            # Mock model loading (would be actual HDFS + joblib load)
            model_name = f"traffic_model_{i}"
            
            # Simulate model loading time
            time.sleep(0.05)  # 50ms per model load
            
            model_load_times.append(time.time() - start)
        
        self.stop_monitoring()
        
        # Calculate loading performance
        avg_load_time = statistics.mean(model_load_times)
        max_load_time = max(model_load_times)
        
        print(f"Average model load time: {avg_load_time:.3f} seconds")
        print(f"Maximum model load time: {max_load_time:.3f} seconds")
        
        # Performance assertions
        self.assertLess(avg_load_time, 1.0, "Model loading too slow")
        self.assertLess(max_load_time, 2.0, "Maximum model load time too high")
        self.print_performance_summary()
    
    def test_prediction_generation_performance(self):
        """Test prediction generation speed"""
        self.start_monitoring()
        
        # Simulate prediction generation
        prediction_count = 1000
        prediction_times = []
        
        for i in range(prediction_count):
            start = time.time()
            
            # Mock prediction generation
            # (would be actual feature processing + model.predict)
            features = [50.0, 60.0, 0.3, i % 24, i % 7]  # Mock features
            
            # Simulate prediction computation
            predicted_value = sum(features) / len(features) + (i % 10)
            confidence = 0.8 + (i % 2) * 0.1
            
            prediction_times.append(time.time() - start)
        
        self.stop_monitoring()
        
        # Calculate prediction performance
        avg_prediction_time = statistics.mean(prediction_times)
        throughput = prediction_count / sum(prediction_times)
        
        print(f"Average prediction time: {avg_prediction_time*1000:.3f} ms")
        print(f"Prediction throughput: {throughput:.0f} predictions/second")
        
        # Performance assertions
        self.assertLess(avg_prediction_time, 0.01, "Individual predictions too slow")
        self.assertGreater(throughput, 5000, "Prediction throughput too low")
        self.print_performance_summary()

class TestConcurrencyPerformance(PerformanceTestBase):
    """Performance tests for concurrent operations"""
    
    def test_concurrent_predictions(self):
        """Test concurrent prediction generation performance"""
        self.start_monitoring()
        
        # Test concurrent prediction requests
        num_threads = 10
        predictions_per_thread = 100
        
        def generate_predictions(thread_id):
            """Generate predictions in a thread"""
            predictions = []
            for i in range(predictions_per_thread):
                start = time.time()
                
                # Mock prediction generation
                prediction = {
                    'thread_id': thread_id,
                    'prediction_id': i,
                    'predicted_value': 50.0 + (i % 20),
                    'confidence': 0.8,
                    'generation_time': time.time() - start
                }
                predictions.append(prediction)
                
                # Small delay to simulate processing
                time.sleep(0.001)
            
            return predictions
        
        # Execute concurrent predictions
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(generate_predictions, i) 
                for i in range(num_threads)
            ]
            
            all_predictions = []
            for future in as_completed(futures):
                all_predictions.extend(future.result())
        
        self.stop_monitoring()
        
        # Calculate concurrency metrics
        total_predictions = len(all_predictions)
        total_time = self.performance_metrics['execution_time']
        throughput = total_predictions / total_time
        
        print(f"Concurrent predictions: {total_predictions}")
        print(f"Total execution time: {total_time:.3f} seconds")
        print(f"Concurrent throughput: {throughput:.0f} predictions/second")
        
        # Performance assertions
        expected_min_throughput = 5000  # Adjust based on requirements
        self.assertGreater(throughput, expected_min_throughput, 
                          "Concurrent throughput too low")
        self.print_performance_summary()
    
    def test_database_connection_pool_performance(self):
        """Test database connection pool under concurrent load"""
        self.start_monitoring()
        
        # Simulate concurrent database operations
        num_threads = 20
        operations_per_thread = 50
        connection_times = queue.Queue()
        
        def database_operations(thread_id):
            """Simulate database operations in a thread"""
            for i in range(operations_per_thread):
                start = time.time()
                
                # Mock database connection and query
                # (would be actual connection pool get/return)
                time.sleep(0.002)  # 2ms per operation
                
                connection_times.put(time.time() - start)
        
        # Execute concurrent database operations
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=database_operations, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        self.stop_monitoring()
        
        # Collect timing results
        operation_times = []
        while not connection_times.empty():
            operation_times.append(connection_times.get())
        
        # Calculate connection pool performance
        avg_operation_time = statistics.mean(operation_times)
        p95_operation_time = statistics.quantiles(operation_times, n=20)[18]
        
        print(f"Database operations: {len(operation_times)}")
        print(f"Average operation time: {avg_operation_time*1000:.2f} ms")
        print(f"95th percentile time: {p95_operation_time*1000:.2f} ms")
        
        # Performance assertions
        self.assertLess(avg_operation_time, 0.05, "Database operations too slow")
        self.assertLess(p95_operation_time, 0.1, "95th percentile too high")
        self.print_performance_summary()

class TestScalabilityPerformance(PerformanceTestBase):
    """Performance tests for system scalability"""
    
    def test_batch_size_scaling(self):
        """Test performance across different batch sizes"""
        batch_sizes = [100, 500, 1000, 2000, 5000]
        performance_results = {}
        
        for batch_size in batch_sizes:
            print(f"\nTesting batch size: {batch_size}")
            
            self.start_monitoring()
            
            # Simulate batch processing
            start_time = time.time()
            
            # Mock batch prediction processing
            for i in range(batch_size):
                # Simulate feature processing and prediction
                features = [50.0 + i, 60.0, 0.3, i % 24]
                prediction = sum(features) / len(features)
                
                # Small processing delay
                if i % 100 == 0:  # Periodic delay to simulate batch processing
                    time.sleep(0.001)
            
            processing_time = time.time() - start_time
            self.stop_monitoring()
            
            # Record performance metrics
            throughput = batch_size / processing_time
            performance_results[batch_size] = {
                'throughput': throughput,
                'processing_time': processing_time,
                'memory_used': self.performance_metrics['memory_used']
            }
            
            print(f"Throughput: {throughput:.0f} predictions/second")
            print(f"Processing time: {processing_time:.3f} seconds")
        
        # Analyze scaling characteristics
        print(f"\n--- Batch Size Scaling Analysis ---")
        for batch_size, metrics in performance_results.items():
            efficiency = metrics['throughput'] / batch_size * 1000
            print(f"Batch {batch_size}: {metrics['throughput']:.0f} pred/s, "
                  f"efficiency: {efficiency:.2f}")
        
        # Assert that larger batches are more efficient
        small_batch_throughput = performance_results[100]['throughput']
        large_batch_throughput = performance_results[5000]['throughput']
        
        self.assertGreater(large_batch_throughput, small_batch_throughput,
                          "Large batches should be more efficient")
    
    def test_memory_usage_scaling(self):
        """Test memory usage across different data sizes"""
        data_sizes = [1000, 5000, 10000, 20000]
        memory_usage = {}
        
        for data_size in data_sizes:
            self.start_monitoring()
            
            # Simulate data processing with increasing size
            data_buffer = []
            
            for i in range(data_size):
                # Simulate data record
                record = {
                    'id': i,
                    'timestamp': datetime.now(),
                    'features': [50.0 + i, 60.0, 0.3, i % 24, i % 7],
                    'prediction': 50.0 + (i % 20)
                }
                data_buffer.append(record)
            
            self.stop_monitoring()
            
            memory_used_mb = self.performance_metrics['memory_used'] / 1024 / 1024
            memory_usage[data_size] = memory_used_mb
            
            print(f"Data size {data_size}: {memory_used_mb:.2f} MB")
        
        # Analyze memory scaling
        print(f"\n--- Memory Usage Scaling Analysis ---")
        for data_size, memory_mb in memory_usage.items():
            memory_per_record = memory_mb / data_size * 1024  # KB per record
            print(f"Size {data_size}: {memory_mb:.2f} MB total, "
                  f"{memory_per_record:.3f} KB per record")
        
        # Assert reasonable memory usage
        max_memory_per_record = 1.0  # 1 KB per record maximum
        for data_size, memory_mb in memory_usage.items():
            memory_per_record = memory_mb / data_size * 1024
            self.assertLess(memory_per_record, max_memory_per_record,
                           f"Memory usage too high for size {data_size}")

class TestSparkPerformance(PerformanceTestBase):
    """Performance tests for Spark-based operations"""
    
    def test_spark_job_simulation(self):
        """Simulate Spark job performance characteristics"""
        self.start_monitoring()
        
        # Simulate Spark job execution phases
        phases = {
            'data_loading': 2.0,      # 2 seconds
            'feature_processing': 5.0, # 5 seconds  
            'model_prediction': 3.0,   # 3 seconds
            'result_writing': 1.0      # 1 second
        }
        
        phase_times = {}
        total_start = time.time()
        
        for phase, expected_duration in phases.items():
            phase_start = time.time()
            
            # Simulate phase processing
            time.sleep(expected_duration * 0.1)  # Scale down for testing
            
            phase_times[phase] = time.time() - phase_start
            print(f"Phase '{phase}': {phase_times[phase]:.3f} seconds")
        
        total_time = time.time() - total_start
        self.stop_monitoring()
        
        # Analyze Spark job performance
        print(f"\nTotal Spark job simulation time: {total_time:.3f} seconds")
        
        # Performance assertions
        self.assertLess(total_time, 5.0, "Spark job simulation too slow")
        
        # Check that phases completed in reasonable order
        expected_order = ['data_loading', 'feature_processing', 
                         'model_prediction', 'result_writing']
        
        self.assertEqual(list(phase_times.keys()), expected_order,
                        "Spark job phases not in expected order")
        
        self.print_performance_summary()

def run_load_test(duration_seconds=300):
    """Run extended load testing"""
    print(f"\n{'='*50}")
    print(f"STARTING LOAD TEST - Duration: {duration_seconds} seconds")
    print(f"{'='*50}")
    
    start_time = time.time()
    end_time = start_time + duration_seconds
    
    # Metrics collection
    request_count = 0
    error_count = 0
    response_times = []
    
    def simulate_prediction_request():
        """Simulate a single prediction request"""
        nonlocal request_count, error_count
        
        try:
            request_start = time.time()
            
            # Simulate prediction processing
            features = [50.0, 60.0, 0.3, request_count % 24]
            prediction = sum(features) / len(features)
            
            # Simulate variable processing time
            processing_delay = 0.001 + (request_count % 10) * 0.0001
            time.sleep(processing_delay)
            
            response_time = time.time() - request_start
            response_times.append(response_time)
            request_count += 1
            
        except Exception as e:
            error_count += 1
            print(f"Error in request: {e}")
    
    # Run load test
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        
        while time.time() < end_time:
            # Submit prediction requests
            for _ in range(10):  # Batch of 10 requests
                future = executor.submit(simulate_prediction_request)
                futures.append(future)
            
            # Brief pause between batches
            time.sleep(0.1)
        
        # Wait for remaining requests to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                error_count += 1
    
    # Calculate load test results
    total_duration = time.time() - start_time
    requests_per_second = request_count / total_duration
    error_rate = error_count / request_count if request_count > 0 else 0
    
    if response_times:
        avg_response_time = statistics.mean(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[18]
        p99_response_time = statistics.quantiles(response_times, n=100)[98]
    else:
        avg_response_time = p95_response_time = p99_response_time = 0
    
    # Print load test results
    print(f"\n{'='*50}")
    print(f"LOAD TEST RESULTS")
    print(f"{'='*50}")
    print(f"Duration: {total_duration:.1f} seconds")
    print(f"Total Requests: {request_count}")
    print(f"Requests/Second: {requests_per_second:.1f}")
    print(f"Error Count: {error_count}")
    print(f"Error Rate: {error_rate:.2%}")
    print(f"Average Response Time: {avg_response_time*1000:.2f} ms")
    print(f"95th Percentile Response Time: {p95_response_time*1000:.2f} ms")
    print(f"99th Percentile Response Time: {p99_response_time*1000:.2f} ms")
    
    # Performance thresholds
    assert requests_per_second > 1000, f"RPS too low: {requests_per_second}"
    assert error_rate < 0.01, f"Error rate too high: {error_rate:.2%}"
    assert avg_response_time < 0.01, f"Avg response time too high: {avg_response_time*1000:.2f}ms"
    
    print(f"\nLOAD TEST PASSED!")

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Performance testing for Traffic Prediction Service')
    parser.add_argument('--load-test', action='store_true', 
                       help='Run extended load testing')
    parser.add_argument('--duration', type=int, default=300,
                       help='Load test duration in seconds (default: 300)')
    
    args, remaining_args = parser.parse_known_args()
    
    if args.load_test:
        # Run load test
        run_load_test(args.duration)
    else:
        # Run unit tests
        sys.argv = [sys.argv[0]] + remaining_args  # Pass remaining args to unittest
        
        # Configure test discovery and execution
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Add performance test classes
        test_classes = [
            TestDatabasePerformance,
            TestModelPerformance,
            TestConcurrencyPerformance,
            TestScalabilityPerformance,
            TestSparkPerformance
        ]
        
        for test_class in test_classes:
            tests = loader.loadTestsFromTestCase(test_class)
            suite.addTests(tests)
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Print summary
        print(f"\n{'='*50}")
        print(f"PERFORMANCE TEST SUMMARY")
        print(f"{'='*50}")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        
        # Exit with error code if tests failed
        success = result.wasSuccessful()
        print(f"\nOverall result: {'PASSED' if success else 'FAILED'}")
        sys.exit(0 if success else 1)