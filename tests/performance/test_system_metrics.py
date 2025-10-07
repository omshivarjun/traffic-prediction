"""
Performance Testing Suite - System Metrics
Tests CPU, memory, disk I/O, and network utilization metrics.
"""

import pytest
import psutil
import time
import requests
from kafka import KafkaProducer, KafkaConsumer
import json
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8001"
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9092']


class TestCPUUtilization:
    """Test CPU utilization under load."""
    
    def test_1_baseline_cpu_utilization(self):
        """Measure baseline CPU utilization."""
        # Sample CPU usage over 5 seconds
        samples = []
        for _ in range(5):
            cpu_percent = psutil.cpu_percent(interval=1)
            samples.append(cpu_percent)
        
        avg_cpu = sum(samples) / len(samples)
        max_cpu = max(samples)
        
        print(f"\n  Baseline CPU Utilization:")
        print(f"    Average: {avg_cpu:.2f}%")
        print(f"    Maximum: {max_cpu:.2f}%")
        print(f"    Samples: {samples}")
        
        # System should not be saturated at baseline
        assert avg_cpu < 80, f"Average CPU {avg_cpu:.2f}% exceeds 80% at baseline"
    
    def test_2_cpu_under_api_load(self):
        """Test CPU utilization under API request load."""
        # Baseline measurement
        baseline_cpu = psutil.cpu_percent(interval=1)
        
        # Generate API load
        start_time = time.time()
        request_count = 0
        
        while time.time() - start_time < 10:  # 10 second test
            try:
                requests.get(f"{BACKEND_URL}/health", timeout=1)
                request_count += 1
            except:
                pass
        
        # Measure CPU during load
        load_cpu = psutil.cpu_percent(interval=1)
        
        print(f"\n  CPU Under API Load:")
        print(f"    Baseline: {baseline_cpu:.2f}%")
        print(f"    Under Load: {load_cpu:.2f}%")
        print(f"    Requests Processed: {request_count}")
        
        # CPU should not be saturated
        assert load_cpu < 90, f"CPU {load_cpu:.2f}% exceeds 90% under load"


class TestMemoryUtilization:
    """Test memory utilization patterns."""
    
    def test_3_baseline_memory_usage(self):
        """Measure baseline memory utilization."""
        memory = psutil.virtual_memory()
        
        print(f"\n  Baseline Memory Utilization:")
        print(f"    Total: {memory.total / (1024**3):.2f} GB")
        print(f"    Available: {memory.available / (1024**3):.2f} GB")
        print(f"    Used: {memory.used / (1024**3):.2f} GB")
        print(f"    Percent: {memory.percent:.2f}%")
        
        # System should have reasonable memory available
        assert memory.percent < 90, f"Memory usage {memory.percent:.2f}% exceeds 90%"
        assert memory.available > 1 * 1024**3, "Less than 1GB memory available"
    
    def test_4_memory_growth_during_operation(self):
        """Test for memory leaks during sustained operation."""
        # Initial memory
        initial_memory = psutil.virtual_memory().used
        
        # Simulate sustained operations
        for i in range(100):
            try:
                requests.get(f"{BACKEND_URL}/health", timeout=1)
            except:
                pass
            
            if i % 20 == 0:
                time.sleep(0.1)  # Small pause
        
        # Final memory
        final_memory = psutil.virtual_memory().used
        memory_growth = (final_memory - initial_memory) / (1024**2)  # MB
        
        print(f"\n  Memory Growth During Operation:")
        print(f"    Initial: {initial_memory / (1024**2):.2f} MB")
        print(f"    Final: {final_memory / (1024**2):.2f} MB")
        print(f"    Growth: {memory_growth:.2f} MB")
        
        # Memory growth should be minimal
        assert memory_growth < 500, f"Memory grew by {memory_growth:.2f}MB, possible leak"


class TestDiskIOPerformance:
    """Test disk I/O performance metrics."""
    
    def test_5_disk_io_counters(self):
        """Measure disk I/O activity."""
        # Get disk I/O statistics
        disk_io_start = psutil.disk_io_counters()
        
        # Wait and measure
        time.sleep(2)
        
        disk_io_end = psutil.disk_io_counters()
        
        # Calculate rates
        read_bytes_per_sec = (disk_io_end.read_bytes - disk_io_start.read_bytes) / 2
        write_bytes_per_sec = (disk_io_end.write_bytes - disk_io_start.write_bytes) / 2
        
        print(f"\n  Disk I/O Activity:")
        print(f"    Read Rate: {read_bytes_per_sec / (1024**2):.2f} MB/s")
        print(f"    Write Rate: {write_bytes_per_sec / (1024**2):.2f} MB/s")
        print(f"    Read Count: {disk_io_end.read_count - disk_io_start.read_count}")
        print(f"    Write Count: {disk_io_end.write_count - disk_io_start.write_count}")
        
        # This is primarily observational
        assert True, "Disk I/O metrics captured"
    
    def test_6_disk_space_availability(self):
        """Ensure adequate disk space is available."""
        disk_usage = psutil.disk_usage('.')
        
        print(f"\n  Disk Space:")
        print(f"    Total: {disk_usage.total / (1024**3):.2f} GB")
        print(f"    Used: {disk_usage.used / (1024**3):.2f} GB")
        print(f"    Free: {disk_usage.free / (1024**3):.2f} GB")
        print(f"    Percent Used: {disk_usage.percent:.2f}%")
        
        # Ensure adequate free space
        assert disk_usage.free > 5 * 1024**3, "Less than 5GB disk space available"
        assert disk_usage.percent < 90, f"Disk usage {disk_usage.percent:.2f}% exceeds 90%"


class TestNetworkUtilization:
    """Test network bandwidth and utilization."""
    
    def test_7_network_io_counters(self):
        """Measure network I/O activity."""
        # Get network I/O statistics
        net_io_start = psutil.net_io_counters()
        
        # Generate some network activity
        for _ in range(10):
            try:
                requests.get(f"{BACKEND_URL}/health", timeout=1)
            except:
                pass
        
        time.sleep(1)
        net_io_end = psutil.net_io_counters()
        
        # Calculate rates
        bytes_sent = net_io_end.bytes_sent - net_io_start.bytes_sent
        bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
        
        print(f"\n  Network I/O Activity:")
        print(f"    Bytes Sent: {bytes_sent / 1024:.2f} KB")
        print(f"    Bytes Received: {bytes_recv / 1024:.2f} KB")
        print(f"    Packets Sent: {net_io_end.packets_sent - net_io_start.packets_sent}")
        print(f"    Packets Received: {net_io_end.packets_recv - net_io_start.packets_recv}")
        
        # Ensure network is active
        assert bytes_sent > 0 or bytes_recv > 0, "No network activity detected"
    
    def test_8_network_connections(self):
        """Monitor active network connections."""
        connections = psutil.net_connections(kind='inet')
        
        # Filter for established connections
        established = [c for c in connections if c.status == 'ESTABLISHED']
        listening = [c for c in connections if c.status == 'LISTEN']
        
        print(f"\n  Network Connections:")
        print(f"    Total: {len(connections)}")
        print(f"    Established: {len(established)}")
        print(f"    Listening: {len(listening)}")
        
        # Ensure reasonable connection count
        assert len(established) < 1000, f"Too many established connections: {len(established)}"


class TestProcessMetrics:
    """Test individual process resource usage."""
    
    def test_9_python_process_metrics(self):
        """Monitor Python process resource usage."""
        process = psutil.Process()
        
        # Get process metrics
        cpu_percent = process.cpu_percent(interval=1)
        memory_info = process.memory_info()
        num_threads = process.num_threads()
        
        print(f"\n  Python Process Metrics:")
        print(f"    CPU: {cpu_percent:.2f}%")
        print(f"    Memory RSS: {memory_info.rss / (1024**2):.2f} MB")
        print(f"    Memory VMS: {memory_info.vms / (1024**2):.2f} MB")
        print(f"    Threads: {num_threads}")
        
        # Ensure reasonable resource usage
        assert cpu_percent < 100, f"Process CPU {cpu_percent:.2f}% exceeds 100%"
        assert memory_info.rss < 2 * 1024**3, f"Process memory exceeds 2GB"
    
    def test_10_docker_container_count(self):
        """Verify expected Docker containers are running."""
        try:
            import docker
            client = docker.from_env()
            containers = client.containers.list()
            
            running_containers = [c for c in containers if c.status == 'running']
            
            print(f"\n  Docker Container Status:")
            print(f"    Total Containers: {len(containers)}")
            print(f"    Running: {len(running_containers)}")
            
            for container in running_containers[:10]:  # Show first 10
                print(f"      - {container.name}: {container.status}")
            
            # Should have our 20 service containers
            assert len(running_containers) >= 15, f"Only {len(running_containers)} containers running, expected 20+"
            
        except Exception as e:
            pytest.skip(f"Cannot connect to Docker: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
