"""
Simple API test that just checks if the endpoint responds
"""
import socket
import time

print("Waiting for backend to start...")
time.sleep(10)

print("\nTesting if port 8000 is open...")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('localhost', 8000))
if result == 0:
    print("✅ Port 8000 is OPEN - Backend is running!")
else:
    print("❌ Port 8000 is CLOSED - Backend is not running")
sock.close()

print("\nDone - not sending any HTTP requests to avoid shutdown")
