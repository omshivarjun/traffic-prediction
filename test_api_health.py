"""
Test script to verify API health endpoint
"""
import requests
import json
import time

# Wait for backend to be fully started
time.sleep(2)

try:
    # Test health endpoint
    print("Testing health endpoint...")
    response = requests.get("http://localhost:8000/health", timeout=5)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    # Test docs endpoint
    print("\n\nTesting docs endpoint...")
    docs_response = requests.get("http://localhost:8000/docs", timeout=5)
    print(f"Docs Status Code: {docs_response.status_code}")
    
    # Test traffic endpoint
    print("\n\nTesting traffic current endpoint...")
    traffic_response = requests.get("http://localhost:8000/api/traffic/current?limit=10", timeout=5)
    print(f"Traffic Status Code: {traffic_response.status_code}")
    print(f"Traffic Response:")
    print(json.dumps(traffic_response.json(), indent=2))
    
except Exception as e:
    print(f"Error: {str(e)}")
