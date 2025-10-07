"""
Integration Test Runner
Comprehensive test execution with reporting
"""

import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path


class IntegrationTestRunner:
    """Run integration tests and generate reports"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.test_dir = self.project_root / "tests" / "integration"
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'test_suites': [],
            'summary': {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0
            }
        }
    
    def run_test_suite(self, test_file: str, description: str) -> dict:
        """Run a single test suite"""
        print(f"\n{'='*80}")
        print(f"Running: {description}")
        print(f"File: {test_file}")
        print(f"{'='*80}\n")
        
        test_path = self.test_dir / test_file
        
        # Run pytest with JSON report
        cmd = [
            sys.executable, "-m", "pytest",
            str(test_path),
            "-v",
            "--tb=short",
            "--json-report",
            "--json-report-file=test_report.json"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            suite_result = {
                'name': description,
                'file': test_file,
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'status': 'passed' if result.returncode == 0 else 'failed'
            }
            
            # Parse test counts from output
            self._parse_test_counts(result.stdout, suite_result)
            
            return suite_result
            
        except subprocess.TimeoutExpired:
            return {
                'name': description,
                'file': test_file,
                'exit_code': -1,
                'status': 'timeout',
                'error': 'Test suite timed out after 5 minutes'
            }
        except Exception as e:
            return {
                'name': description,
                'file': test_file,
                'exit_code': -1,
                'status': 'error',
                'error': str(e)
            }
    
    def _parse_test_counts(self, output: str, suite_result: dict):
        """Parse test counts from pytest output"""
        # Look for pytest summary line
        lines = output.split('\n')
        for line in lines:
            if 'passed' in line or 'failed' in line:
                if 'passed' in line:
                    try:
                        passed = int(line.split('passed')[0].split()[-1])
                        suite_result['passed'] = passed
                        self.results['summary']['passed'] += passed
                        self.results['summary']['total'] += passed
                    except:
                        pass
                
                if 'failed' in line:
                    try:
                        failed = int(line.split('failed')[0].split()[-1])
                        suite_result['failed'] = failed
                        self.results['summary']['failed'] += failed
                        self.results['summary']['total'] += failed
                    except:
                        pass
                
                if 'skipped' in line:
                    try:
                        skipped = int(line.split('skipped')[0].split()[-1])
                        suite_result['skipped'] = skipped
                        self.results['summary']['skipped'] += skipped
                        self.results['summary']['total'] += skipped
                    except:
                        pass
    
    def run_all_tests(self):
        """Run all integration test suites"""
        print("\n" + "="*80)
        print("TRAFFIC PREDICTION SYSTEM - INTEGRATION TEST SUITE")
        print("="*80)
        print(f"Started at: {datetime.utcnow().isoformat()}")
        print("="*80 + "\n")
        
        # Define test suites to run
        test_suites = [
            {
                'file': 'test_database_api_integration.py',
                'description': 'Database + API Integration Tests'
            },
            {
                'file': 'test_kafka_stream_integration.py',
                'description': 'Kafka + Stream Processor Integration Tests'
            },
            {
                'file': 'test_frontend_backend_integration.py',
                'description': 'Frontend + Backend Integration Tests'
            }
        ]
        
        # Run each test suite
        for suite in test_suites:
            suite_result = self.run_test_suite(suite['file'], suite['description'])
            self.results['test_suites'].append(suite_result)
            
            # Print immediate result
            status_icon = "✅" if suite_result['status'] == 'passed' else "❌"
            print(f"\n{status_icon} {suite['description']}: {suite_result['status'].upper()}")
        
        # Generate final report
        self._generate_report()
    
    def _generate_report(self):
        """Generate and save test report"""
        print("\n" + "="*80)
        print("TEST EXECUTION SUMMARY")
        print("="*80)
        
        summary = self.results['summary']
        total = summary['total']
        passed = summary['passed']
        failed = summary['failed']
        skipped = summary['skipped']
        
        print(f"\nTotal Tests:   {total}")
        print(f"✅ Passed:     {passed}")
        print(f"❌ Failed:     {failed}")
        print(f"⏭️  Skipped:    {skipped}")
        
        if total > 0:
            pass_rate = (passed / total) * 100
            print(f"\nPass Rate:     {pass_rate:.1f}%")
        
        # Overall status
        print("\n" + "="*80)
        if failed == 0 and total > 0:
            print("✅ ALL INTEGRATION TESTS PASSED")
        elif total == 0:
            print("⚠️  NO TESTS WERE RUN")
        else:
            print(f"❌ {failed} TEST(S) FAILED")
        print("="*80 + "\n")
        
        # Save detailed results
        report_file = self.project_root / f"integration_test_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"Detailed results saved to: {report_file}\n")
        except Exception as e:
            print(f"Warning: Could not save detailed results: {e}\n")
        
        # Exit with appropriate code
        sys.exit(0 if failed == 0 and total > 0 else 1)


def main():
    """Main entry point"""
    runner = IntegrationTestRunner()
    runner.run_all_tests()


if __name__ == "__main__":
    main()
