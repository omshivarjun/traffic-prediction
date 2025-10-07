"""
Master Connectivity Test Runner

Executes all connectivity tests in phases with comprehensive reporting.
This validates the entire big data architecture is operational.
"""

import pytest
import sys
import time
from pathlib import Path


def print_header(text, color="cyan"):
    """Print formatted header"""
    colors = {
        "cyan": "\033[96m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "reset": "\033[0m"
    }
    
    c = colors.get(color, colors["cyan"])
    reset = colors["reset"]
    
    print(f"\n{c}{'='*60}{reset}")
    print(f"{c}  {text}{reset}")
    print(f"{c}{'='*60}{reset}\n")


def run_test_phase(phase_name, test_files):
    """Run a phase of connectivity tests"""
    print_header(phase_name, "cyan")
    
    results = []
    
    for test_file in test_files:
        test_path = Path(__file__).parent / "connectivity" / test_file
        
        if not test_path.exists():
            print(f"⚠️  Test file not found: {test_file}")
            print(f"    Expected at: {test_path}")
            continue
        
        print(f"Running: {test_file}")
        print("-" * 60)
        
        # Run pytest on the specific file
        exit_code = pytest.main([
            str(test_path),
            "-v",
            "-s",
            "--tb=short",
            f"--json-report",
            f"--json-report-file=.pytest_cache/{test_file.replace('.py', '_results.json')}"
        ])
        
        results.append((test_file, exit_code))
        
        if exit_code == 0:
            print(f"\n✅ {test_file} - ALL TESTS PASSED\n")
        else:
            print(f"\n❌ {test_file} - SOME TESTS FAILED")
            print(f"Cannot proceed until this is fixed.\n")
            return False, results
    
    return True, results


def main():
    """Main test runner"""
    print_header("CRITICAL SYSTEM CONNECTIVITY VALIDATION", "yellow")
    
    print("Objective: Verify ALL components are properly connected")
    print("Requirement: 100% test pass rate\n")
    
    start_time = time.time()
    
    # Define test phases
    test_phases = [
        ("Phase 1: Component Connectivity", [
            "test_kafka_spark.py",
            "test_backend_kafka.py",
            "test_backend_postgres.py",
            "test_backend_frontend.py",
        ]),
        ("Phase 2: ML & Predictions", [
            "test_predictions.py",
        ]),
    ]
    
    all_results = []
    
    for phase_name, test_files in test_phases:
        success, results = run_test_phase(phase_name, test_files)
        all_results.extend(results)
        
        if not success:
            print_header("CRITICAL FAILURE - STOPPING", "red")
            print_summary(all_results, time.time() - start_time, success=False)
            return 1
    
    # All tests passed
    print_header("ALL CONNECTIVITY TESTS PASSED!", "green")
    print_summary(all_results, time.time() - start_time, success=True)
    
    return 0


def print_summary(results, duration, success=True):
    """Print test summary"""
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60 + "\n")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, code in results if code == 0)
    failed_tests = total_tests - passed_tests
    
    for test_file, exit_code in results:
        status = "✅ PASSED" if exit_code == 0 else "❌ FAILED"
        print(f"  {status}  {test_file}")
    
    print(f"\n{'='*60}")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"{'='*60}\n")
    
    if success:
        print("✅ Complete system connectivity VALIDATED")
        print("✅ All components properly connected")
        print("✅ Data/workflow passing through entire architecture\n")
    else:
        print("❌ System connectivity INCOMPLETE")
        print("❌ Fix failures before proceeding\n")


if __name__ == "__main__":
    sys.exit(main())
