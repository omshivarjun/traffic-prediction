"""
Test runner script for FastAPI backend
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add the API module to the path
api_path = Path(__file__).parent.parent
sys.path.insert(0, str(api_path))


def run_unit_tests():
    """Run unit tests using pytest"""
    print("Running unit tests...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--disable-warnings",
        "--cov=src/api",
        "--cov-report=html:htmlcov",
        "--cov-report=term-missing"
    ]
    
    result = subprocess.run(cmd, cwd=api_path)
    return result.returncode == 0


def run_integration_tests():
    """Run integration tests"""
    print("Running integration tests...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_websocket_endpoints.py",
        "-v",
        "--tb=short",
        "--disable-warnings"
    ]
    
    result = subprocess.run(cmd, cwd=api_path)
    return result.returncode == 0


def run_load_tests(host="localhost", port=8000, users=10, spawn_rate=2, duration="60s"):
    """Run load tests using Locust"""
    print(f"Running load tests against {host}:{port}...")
    print(f"Users: {users}, Spawn rate: {spawn_rate}/s, Duration: {duration}")
    
    cmd = [
        sys.executable, "-m", "locust",
        "-f", "tests/load_test.py",
        "--host", f"http://{host}:{port}",
        "--users", str(users),
        "--spawn-rate", str(spawn_rate),
        "--run-time", duration,
        "--headless",
        "--html", "load_test_report.html"
    ]
    
    result = subprocess.run(cmd, cwd=api_path)
    return result.returncode == 0


def check_dependencies():
    """Check if required test dependencies are installed"""
    required_packages = [
        "pytest",
        "pytest-cov",
        "pytest-asyncio",
        "locust",
        "testcontainers"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Missing required packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nInstall missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True


def setup_test_environment():
    """Setup test environment variables"""
    test_env = {
        "TESTING": "true",
        "DATABASE_URL": "sqlite:///./test_traffic.db",
        "KAFKA_ENABLED": "false",
        "LOG_LEVEL": "DEBUG"
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
    
    print("Test environment configured")


def clean_test_artifacts():
    """Clean up test artifacts"""
    artifacts = [
        "test_traffic.db",
        "load_test_report.html",
        "htmlcov/",
        ".coverage",
        "__pycache__/",
        ".pytest_cache/"
    ]
    
    for artifact in artifacts:
        artifact_path = api_path / artifact
        if artifact_path.exists():
            if artifact_path.is_file():
                artifact_path.unlink()
                print(f"Removed {artifact}")
            elif artifact_path.is_dir():
                import shutil
                shutil.rmtree(artifact_path)
                print(f"Removed {artifact}/")


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="FastAPI Test Runner")
    parser.add_argument("--type", choices=["unit", "integration", "load", "all"], 
                       default="all", help="Type of tests to run")
    parser.add_argument("--host", default="localhost", help="Host for load testing")
    parser.add_argument("--port", type=int, default=8000, help="Port for load testing")
    parser.add_argument("--users", type=int, default=10, help="Number of users for load testing")
    parser.add_argument("--spawn-rate", type=int, default=2, help="User spawn rate for load testing")
    parser.add_argument("--duration", default="60s", help="Duration for load testing")
    parser.add_argument("--clean", action="store_true", help="Clean test artifacts before running")
    parser.add_argument("--check-deps", action="store_true", help="Check test dependencies")
    
    args = parser.parse_args()
    
    if args.check_deps:
        if check_dependencies():
            print("All required dependencies are installed")
        return
    
    if args.clean:
        clean_test_artifacts()
    
    setup_test_environment()
    
    success = True
    
    if args.type in ["unit", "all"]:
        success = success and run_unit_tests()
    
    if args.type in ["integration", "all"]:
        success = success and run_integration_tests()
    
    if args.type in ["load", "all"]:
        success = success and run_load_tests(
            host=args.host,
            port=args.port,
            users=args.users,
            spawn_rate=args.spawn_rate,
            duration=args.duration
        )
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()