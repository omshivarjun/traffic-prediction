#!/usr/bin/env python3
"""
Test Runner for Traffic Prediction Service

Comprehensive test execution script that runs all test suites including:
- Unit tests for individual components
- Integration tests for end-to-end workflows  
- Performance benchmarks and load testing
- Configuration validation and environment checks

Usage:
    python tests/run_tests.py                    # Run all tests
    python tests/run_tests.py --unit             # Run only unit tests
    python tests/run_tests.py --integration      # Run only integration tests
    python tests/run_tests.py --performance      # Run only performance tests
    python tests/run_tests.py --load-test        # Run extended load testing
    python tests/run_tests.py --quick            # Run quick test suite
"""

import os
import sys
import argparse
import subprocess
import time
import json
from datetime import datetime

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

class TestRunner:
    """Comprehensive test runner for prediction service"""
    
    def __init__(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.tests_dir = os.path.join(self.project_root, 'tests')
        self.results = {}
        self.start_time = None
        self.total_duration = 0
    
    def print_header(self, title):
        """Print formatted test section header"""
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")
    
    def print_summary(self):
        """Print comprehensive test results summary"""
        self.print_header("TEST EXECUTION SUMMARY")
        
        print(f"Execution Time: {self.total_duration:.2f} seconds")
        print(f"Start Time: {self.start_time}")
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        total_tests = 0
        total_failures = 0
        total_errors = 0
        
        for test_suite, results in self.results.items():
            if results:
                tests_run = results.get('tests_run', 0)
                failures = results.get('failures', 0) 
                errors = results.get('errors', 0)
                
                total_tests += tests_run
                total_failures += failures
                total_errors += errors
                
                status = "PASSED" if (failures == 0 and errors == 0) else "FAILED"
                print(f"\n{test_suite}:")
                print(f"  Tests: {tests_run}, Failures: {failures}, Errors: {errors} - {status}")
        
        print(f"\nOverall Results:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Total Failures: {total_failures}")
        print(f"  Total Errors: {total_errors}")
        
        overall_success = (total_failures == 0 and total_errors == 0)
        print(f"  Overall Status: {'PASSED' if overall_success else 'FAILED'}")
        
        return overall_success
    
    def run_python_tests(self, test_file, test_name=""):
        """Run Python test file and parse results"""
        print(f"\nRunning {test_name or test_file}...")
        
        try:
            # Run the test file
            cmd = [sys.executable, test_file]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=self.project_root,
                timeout=300  # 5 minute timeout
            )
            
            # Parse output for test results
            output = result.stdout + result.stderr
            print(output)
            
            # Simple result parsing (could be enhanced)
            tests_run = output.count('test_')
            failures = output.count('FAIL') + output.count('AssertionError')
            errors = output.count('ERROR') + output.count('Exception:')
            
            # Consider success if return code is 0 and no obvious failures
            success = (result.returncode == 0 and failures == 0 and errors == 0)
            
            return {
                'success': success,
                'tests_run': tests_run,
                'failures': failures,
                'errors': errors,
                'output': output
            }
            
        except subprocess.TimeoutExpired:
            print(f"Test timed out: {test_file}")
            return {
                'success': False,
                'tests_run': 0,
                'failures': 0,
                'errors': 1,
                'output': 'Test timed out'
            }
        except Exception as e:
            print(f"Error running test: {e}")
            return {
                'success': False,
                'tests_run': 0,
                'failures': 0,
                'errors': 1,
                'output': str(e)
            }
    
    def run_unit_tests(self):
        """Run unit test suite"""
        self.print_header("UNIT TESTS")
        
        unit_test_file = os.path.join(self.tests_dir, 'test_prediction_service.py')
        
        if os.path.exists(unit_test_file):
            results = self.run_python_tests(unit_test_file, "Unit Tests")
            self.results['Unit Tests'] = results
            return results['success']
        else:
            print("Unit test file not found, skipping...")
            self.results['Unit Tests'] = None
            return True
    
    def run_integration_tests(self):
        """Run integration test suite"""
        self.print_header("INTEGRATION TESTS")
        
        integration_test_file = os.path.join(self.tests_dir, 'test_integration.py')
        
        if os.path.exists(integration_test_file):
            results = self.run_python_tests(integration_test_file, "Integration Tests") 
            self.results['Integration Tests'] = results
            return results['success']
        else:
            print("Integration test file not found, skipping...")
            self.results['Integration Tests'] = None
            return True
    
    def run_performance_tests(self, load_test=False):
        """Run performance test suite"""
        self.print_header("PERFORMANCE TESTS")
        
        performance_test_file = os.path.join(self.tests_dir, 'test_performance.py')
        
        if os.path.exists(performance_test_file):
            # Add load test flag if requested
            cmd = [sys.executable, performance_test_file]
            if load_test:
                cmd.extend(['--load-test', '--duration=60'])  # Shorter load test for CI
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=600  # 10 minute timeout for performance tests
                )
                
                output = result.stdout + result.stderr
                print(output)
                
                success = result.returncode == 0
                self.results['Performance Tests'] = {
                    'success': success,
                    'tests_run': 1 if load_test else output.count('test_'),
                    'failures': 0 if success else 1,
                    'errors': 0,
                    'output': output
                }
                
                return success
                
            except subprocess.TimeoutExpired:
                print("Performance tests timed out")
                self.results['Performance Tests'] = {
                    'success': False,
                    'tests_run': 0,
                    'failures': 0,
                    'errors': 1,
                    'output': 'Performance tests timed out'
                }
                return False
            
        else:
            print("Performance test file not found, skipping...")
            self.results['Performance Tests'] = None
            return True
    
    def check_environment(self):
        """Check test environment and dependencies"""
        self.print_header("ENVIRONMENT CHECK")
        
        checks = []
        
        # Check Python version
        python_version = sys.version
        print(f"Python Version: {python_version}")
        checks.append(("Python Version", python_version))
        
        # Check for required directories
        required_dirs = [
            'src/prediction',
            'scripts',
            'config',
            'tests'
        ]
        
        for dir_path in required_dirs:
            full_path = os.path.join(self.project_root, dir_path)
            exists = os.path.exists(full_path)
            status = "✓" if exists else "✗"
            print(f"Directory {dir_path}: {status}")
            checks.append((f"Directory {dir_path}", exists))
        
        # Check for key files
        key_files = [
            'src/prediction/prediction_service.py',
            'src/prediction/spark_prediction_job.py',
            'src/prediction/monitoring_system.py', 
            'src/prediction/retraining_pipeline.py',
            'scripts/manage-prediction-service.ps1'
        ]
        
        for file_path in key_files:
            full_path = os.path.join(self.project_root, file_path)
            exists = os.path.exists(full_path)
            status = "✓" if exists else "✗"
            print(f"File {file_path}: {status}")
            checks.append((f"File {file_path}", exists))
        
        # Check for configuration files
        config_files = [
            'src/prediction/prediction_service_config.json'
        ]
        
        for config_file in config_files:
            full_path = os.path.join(self.project_root, config_file)
            exists = os.path.exists(full_path)
            
            if exists:
                try:
                    with open(full_path, 'r') as f:
                        json.load(f)
                    status = "✓ Valid JSON"
                    valid = True
                except json.JSONDecodeError:
                    status = "✗ Invalid JSON"
                    valid = False
            else:
                status = "✗ Not Found"
                valid = False
            
            print(f"Config {config_file}: {status}")
            checks.append((f"Config {config_file}", valid))
        
        # Summary
        failed_checks = [name for name, result in checks if not result]
        
        if failed_checks:
            print(f"\nFailed Environment Checks:")
            for check in failed_checks:
                print(f"  - {check}")
            return False
        else:
            print(f"\nAll environment checks passed ✓")
            return True
    
    def run_quick_tests(self):
        """Run a quick subset of tests for rapid feedback"""
        self.print_header("QUICK TEST SUITE")
        
        print("Running quick validation tests...")
        
        # Just run environment check and basic import tests
        env_ok = self.check_environment()
        
        # Try to import main modules
        import_tests = []
        modules_to_test = [
            ('src.prediction.prediction_service', 'Prediction Service'),
            ('src.prediction.spark_prediction_job', 'Spark Job'),
            ('src.prediction.monitoring_system', 'Monitoring System'),
            ('src.prediction.retraining_pipeline', 'Retraining Pipeline')
        ]
        
        for module_path, module_name in modules_to_test:
            try:
                # Add src to path temporarily
                sys.path.insert(0, os.path.join(self.project_root, 'src'))
                
                # Try importing (this will fail if there are syntax errors)
                __import__(module_path.replace('/', '.'))
                print(f"✓ {module_name} import successful")
                import_tests.append(True)
                
            except ImportError as e:
                print(f"✗ {module_name} import failed: {e}")
                import_tests.append(False)
            except Exception as e:
                print(f"✗ {module_name} error: {e}")
                import_tests.append(False)
            finally:
                # Remove src from path
                if os.path.join(self.project_root, 'src') in sys.path:
                    sys.path.remove(os.path.join(self.project_root, 'src'))
        
        all_imports_ok = all(import_tests)
        
        quick_success = env_ok and all_imports_ok
        
        self.results['Quick Tests'] = {
            'success': quick_success,
            'tests_run': len(modules_to_test) + len([1]),  # imports + env check
            'failures': 0 if quick_success else 1,
            'errors': 0,
            'output': 'Quick validation tests'
        }
        
        return quick_success
    
    def run_all_tests(self, unit=True, integration=True, performance=True, load_test=False):
        """Run complete test suite"""
        self.start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start_timestamp = time.time()
        
        self.print_header("TRAFFIC PREDICTION SERVICE - TEST EXECUTION")
        print(f"Start Time: {self.start_time}")
        
        # Environment check first
        env_ok = self.check_environment()
        if not env_ok:
            print("Environment check failed. Aborting test execution.")
            return False
        
        success = True
        
        # Run test suites based on parameters
        if unit:
            success &= self.run_unit_tests()
        
        if integration:
            success &= self.run_integration_tests()
        
        if performance:
            success &= self.run_performance_tests(load_test=load_test)
        
        # Calculate total duration
        self.total_duration = time.time() - start_timestamp
        
        # Print summary
        overall_success = self.print_summary()
        
        return overall_success

def main():
    """Main test runner entry point"""
    parser = argparse.ArgumentParser(
        description='Test runner for Traffic Prediction Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/run_tests.py                    # Run all tests
  python tests/run_tests.py --unit             # Run only unit tests  
  python tests/run_tests.py --integration      # Run only integration tests
  python tests/run_tests.py --performance      # Run only performance tests
  python tests/run_tests.py --load-test        # Run performance with load testing
  python tests/run_tests.py --quick            # Run quick validation tests
        """
    )
    
    parser.add_argument('--unit', action='store_true',
                       help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', 
                       help='Run integration tests only')
    parser.add_argument('--performance', action='store_true',
                       help='Run performance tests only')
    parser.add_argument('--load-test', action='store_true',
                       help='Include load testing in performance tests')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick validation tests only')
    
    args = parser.parse_args()
    
    # Create test runner
    runner = TestRunner()
    
    # Determine which tests to run
    if args.quick:
        success = runner.run_quick_tests()
    elif args.unit or args.integration or args.performance:
        # Run specific test suites
        success = runner.run_all_tests(
            unit=args.unit,
            integration=args.integration,
            performance=args.performance,
            load_test=args.load_test
        )
    else:
        # Run all tests by default
        success = runner.run_all_tests(
            unit=True,
            integration=True, 
            performance=True,
            load_test=args.load_test
        )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()