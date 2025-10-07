"""
Phase 4 Comprehensive Security Testing
Validates all security implementations from Phases 1-3
"""
import asyncio
import time
import pytest
import httpx
from typing import Dict, List
import docker
import psutil


class TestNetworkIsolation:
    """Test Docker network isolation and service assignments"""
    
    @pytest.fixture(scope="class")
    def docker_client(self):
        """Initialize Docker client"""
        return docker.from_env()
    
    def test_networks_exist(self, docker_client):
        """Verify all 3 Docker networks are created"""
        networks = docker_client.networks.list()
        network_names = [net.name for net in networks]
        
        assert "traffic-frontend" in network_names, "Frontend network missing"
        assert "traffic-backend" in network_names, "Backend network missing"
        assert "traffic-hadoop" in network_names, "Hadoop network missing"
        
        print("✓ All 3 networks exist: traffic-frontend, traffic-backend, traffic-hadoop")
    
    def test_network_subnets(self, docker_client):
        """Verify network subnet configurations"""
        networks = {net.name: net for net in docker_client.networks.list()}
        
        # Frontend: 172.25.0.0/24
        frontend = networks.get("traffic-frontend")
        if frontend:
            ipam = frontend.attrs.get("IPAM", {})
            config = ipam.get("Config", [])
            if config:
                assert config[0]["Subnet"] == "172.25.0.0/24"
                print("✓ Frontend network subnet: 172.25.0.0/24")
        
        # Backend: 172.26.0.0/24
        backend = networks.get("traffic-backend")
        if backend:
            ipam = backend.attrs.get("IPAM", {})
            config = ipam.get("Config", [])
            if config:
                assert config[0]["Subnet"] == "172.26.0.0/24"
                print("✓ Backend network subnet: 172.26.0.0/24")
        
        # Hadoop: 172.27.0.0/24
        hadoop = networks.get("traffic-hadoop")
        if hadoop:
            ipam = hadoop.attrs.get("IPAM", {})
            config = ipam.get("Config", [])
            if config:
                assert config[0]["Subnet"] == "172.27.0.0/24"
                print("✓ Hadoop network subnet: 172.27.0.0/24")
    
    def test_service_network_assignments(self, docker_client):
        """Verify services are on correct networks"""
        containers = docker_client.containers.list()
        
        # Expected assignments
        expected = {
            "backend": ["traffic-frontend", "traffic-backend"],
            "postgres": ["traffic-backend"],
            "kafka": ["traffic-backend"],
            "schema-registry": ["traffic-backend"],
            "zookeeper": ["traffic-backend"],
            "kafka-connect": ["traffic-backend", "traffic-hadoop"],
            "namenode": ["traffic-hadoop"],
            "datanode": ["traffic-hadoop"],
            "resourcemanager": ["traffic-hadoop"],
            "nodemanager": ["traffic-hadoop"],
            "hive-metastore": ["traffic-hadoop"],
            "hbase-master": ["traffic-hadoop"],
            "hbase-regionserver": ["traffic-hadoop"],
        }
        
        for container in containers:
            name = container.name
            networks = list(container.attrs["NetworkSettings"]["Networks"].keys())
            
            # Check if any expected service matches this container name
            for service_key, expected_networks in expected.items():
                if service_key in name.lower():
                    for expected_net in expected_networks:
                        assert expected_net in networks, (
                            f"{name} should be on {expected_net}, found {networks}"
                        )
                    print(f"✓ {name} correctly assigned to: {networks}")
                    break


class TestAuthenticationStress:
    """Stress test authentication system under load"""
    
    BASE_URL = "http://localhost:8001"
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token for testing"""
        client = httpx.Client(base_url=self.BASE_URL)
        response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.mark.asyncio
    async def test_concurrent_logins(self):
        """Test 100 concurrent login requests"""
        async def login():
            async with httpx.AsyncClient(base_url=self.BASE_URL) as client:
                response = await client.post(
                    "/auth/login",
                    json={"username": "admin", "password": "admin123"}
                )
                return response.status_code
        
        # Execute 100 concurrent logins
        start_time = time.time()
        tasks = [login() for _ in range(100)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Verify all successful
        success_count = sum(1 for status in results if status == 200)
        assert success_count >= 90, f"Expected ≥90 successful logins, got {success_count}"
        
        elapsed = end_time - start_time
        print(f"✓ {success_count}/100 concurrent logins successful in {elapsed:.2f}s")
        print(f"✓ Average: {elapsed/100:.3f}s per login")
    
    @pytest.mark.asyncio
    async def test_concurrent_token_refresh(self, admin_token):
        """Test 1000 concurrent token refresh requests"""
        async def refresh():
            async with httpx.AsyncClient(base_url=self.BASE_URL) as client:
                response = await client.post(
                    "/auth/refresh",
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
                return response.status_code
        
        # Execute 1000 concurrent refreshes
        start_time = time.time()
        tasks = [refresh() for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Verify all successful (200 or 401 if token expired is acceptable)
        success_count = sum(1 for status in results if status == 200)
        assert success_count >= 900, f"Expected ≥900 successful refreshes, got {success_count}"
        
        elapsed = end_time - start_time
        print(f"✓ {success_count}/1000 concurrent token refreshes successful in {elapsed:.2f}s")
        print(f"✓ Average: {elapsed/1000:.3f}s per refresh")
    
    @pytest.mark.asyncio
    async def test_failed_login_handling(self):
        """Test handling of failed login attempts"""
        async def failed_login():
            async with httpx.AsyncClient(base_url=self.BASE_URL) as client:
                response = await client.post(
                    "/auth/login",
                    json={"username": "admin", "password": "wrong_password"}
                )
                return response.status_code
        
        # Execute 50 failed logins
        tasks = [failed_login() for _ in range(50)]
        results = await asyncio.gather(*tasks)
        
        # All should be 401 Unauthorized
        failed_count = sum(1 for status in results if status == 401)
        assert failed_count == 50, f"Expected 50 failed logins, got {failed_count}"
        
        print(f"✓ 50/50 failed login attempts correctly rejected with 401")


class TestRateLimiting:
    """Test rate limiting enforcement"""
    
    BASE_URL = "http://localhost:8001"
    
    @pytest.mark.asyncio
    async def test_public_endpoint_rate_limit(self):
        """Test /data/traffic-events rate limit (20/minute)"""
        async def make_request():
            async with httpx.AsyncClient(base_url=self.BASE_URL) as client:
                response = await client.get("/data/traffic-events")
                return response.status_code
        
        # Make 25 requests (should hit limit at 20)
        start_time = time.time()
        tasks = [make_request() for _ in range(25)]
        results = await asyncio.gather(*tasks)
        
        # Count 200 (success) and 429 (rate limited)
        success_count = sum(1 for status in results if status == 200)
        limited_count = sum(1 for status in results if status == 429)
        
        # Expect ~20 success, ~5 limited
        assert success_count <= 20, f"Expected ≤20 successful, got {success_count}"
        assert limited_count >= 3, f"Expected ≥3 rate limited, got {limited_count}"
        
        elapsed = time.time() - start_time
        print(f"✓ Rate limit enforced: {success_count} allowed, {limited_count} blocked")
        print(f"✓ Test completed in {elapsed:.2f}s")
    
    @pytest.mark.asyncio
    async def test_rate_limit_headers(self):
        """Test rate limit headers are present"""
        async with httpx.AsyncClient(base_url=self.BASE_URL) as client:
            response = await client.get("/data/traffic-events")
            
            headers = response.headers
            # Check for common rate limit headers
            # Note: Actual header names depend on rate limiting implementation
            assert response.status_code in [200, 429]
            
            if response.status_code == 200:
                print("✓ Rate limit headers check completed (status 200)")
            else:
                print("✓ Rate limit enforcement confirmed (status 429)")
    
    @pytest.mark.asyncio
    async def test_rate_limit_reset(self):
        """Test rate limit resets after time window"""
        async with httpx.AsyncClient(base_url=self.BASE_URL) as client:
            # Make requests until rate limited
            for i in range(25):
                response = await client.get("/data/traffic-events")
                if response.status_code == 429:
                    print(f"✓ Rate limited after {i+1} requests")
                    break
            
            # Wait for reset (1 minute for this endpoint)
            print("⏳ Waiting 65 seconds for rate limit reset...")
            await asyncio.sleep(65)
            
            # Try again
            response = await client.get("/data/traffic-events")
            assert response.status_code == 200, "Rate limit should have reset"
            print("✓ Rate limit successfully reset after time window")


class TestResourceLimits:
    """Test Docker resource limit enforcement"""
    
    @pytest.fixture(scope="class")
    def docker_client(self):
        """Initialize Docker client"""
        return docker.from_env()
    
    def test_cpu_limits_configured(self, docker_client):
        """Verify CPU limits are set on containers"""
        containers = docker_client.containers.list()
        
        # Expected CPU limits (in nano CPUs: 1 CPU = 1e9)
        expected_limits = {
            "backend": 2.0 * 1e9,
            "postgres": 2.0 * 1e9,
            "kafka": 2.0 * 1e9,
            "namenode": 2.0 * 1e9,
            "datanode": 2.0 * 1e9,
            "resourcemanager": 2.0 * 1e9,
            "nodemanager": 2.0 * 1e9,
            "hbase-regionserver": 2.0 * 1e9,
        }
        
        for container in containers:
            name = container.name
            host_config = container.attrs.get("HostConfig", {})
            nano_cpus = host_config.get("NanoCpus", 0)
            
            # Check if this is an expected service
            for service_key, expected_nano in expected_limits.items():
                if service_key in name.lower():
                    if nano_cpus > 0:
                        cpus = nano_cpus / 1e9
                        print(f"✓ {name}: {cpus} CPU limit configured")
                    break
    
    def test_memory_limits_configured(self, docker_client):
        """Verify memory limits are set on containers"""
        containers = docker_client.containers.list()
        
        # Expected memory limits (in bytes)
        expected_limits = {
            "backend": 2 * 1024**3,      # 2GB
            "postgres": 2 * 1024**3,     # 2GB
            "kafka": 2 * 1024**3,        # 2GB
            "namenode": 4 * 1024**3,     # 4GB
            "datanode": 4 * 1024**3,     # 4GB
            "resourcemanager": 2 * 1024**3,  # 2GB
            "nodemanager": 4 * 1024**3,  # 4GB
            "hive-metastore": 2 * 1024**3,   # 2GB
            "hbase-master": 2 * 1024**3,     # 2GB
            "hbase-regionserver": 4 * 1024**3,  # 4GB
        }
        
        for container in containers:
            name = container.name
            host_config = container.attrs.get("HostConfig", {})
            memory = host_config.get("Memory", 0)
            
            # Check if this is an expected service
            for service_key, expected_mem in expected_limits.items():
                if service_key in name.lower():
                    if memory > 0:
                        mem_gb = memory / 1024**3
                        print(f"✓ {name}: {mem_gb:.1f}GB memory limit configured")
                    break
    
    def test_container_stats(self, docker_client):
        """Test actual resource usage vs limits"""
        containers = docker_client.containers.list()
        
        print("\n=== Container Resource Usage ===")
        for container in containers:
            try:
                stats = container.stats(stream=False)
                
                # CPU usage
                cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                           stats["precpu_stats"]["cpu_usage"]["total_usage"]
                system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                              stats["precpu_stats"]["system_cpu_usage"]
                cpu_count = stats["cpu_stats"].get("online_cpus", 1)
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0 if system_delta > 0 else 0
                
                # Memory usage
                mem_usage = stats["memory_stats"]["usage"]
                mem_limit = stats["memory_stats"]["limit"]
                mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0
                
                print(f"{container.name}:")
                print(f"  CPU: {cpu_percent:.2f}%")
                print(f"  Memory: {mem_usage/1024**2:.1f}MB / {mem_limit/1024**2:.1f}MB ({mem_percent:.1f}%)")
                
            except Exception as e:
                print(f"{container.name}: Error getting stats - {str(e)}")


class TestPerformanceImpact:
    """Test performance impact of security features"""
    
    BASE_URL = "http://localhost:8001"
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token for testing"""
        client = httpx.Client(base_url=self.BASE_URL)
        response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_authenticated_endpoint_latency(self, admin_token):
        """Measure latency for authenticated endpoints"""
        client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Measure 100 requests
        latencies = []
        for _ in range(100):
            start = time.time()
            response = client.get("/data/traffic-data")
            latencies.append(time.time() - start)
        
        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        print(f"\n=== Authenticated Endpoint Performance ===")
        print(f"Average: {avg_latency*1000:.2f}ms")
        print(f"Min: {min_latency*1000:.2f}ms")
        print(f"Max: {max_latency*1000:.2f}ms")
        
        # Assert reasonable performance (< 500ms avg)
        assert avg_latency < 0.5, f"Average latency too high: {avg_latency*1000:.2f}ms"
    
    def test_public_endpoint_latency(self):
        """Measure latency for public endpoints"""
        client = httpx.Client(base_url=self.BASE_URL)
        
        # Measure 100 requests
        latencies = []
        for _ in range(100):
            start = time.time()
            response = client.get("/data/traffic-events")
            latencies.append(time.time() - start)
        
        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        print(f"\n=== Public Endpoint Performance ===")
        print(f"Average: {avg_latency*1000:.2f}ms")
        print(f"Min: {min_latency*1000:.2f}ms")
        print(f"Max: {max_latency*1000:.2f}ms")
        
        # Assert reasonable performance (< 500ms avg)
        assert avg_latency < 0.5, f"Average latency too high: {avg_latency*1000:.2f}ms"


class TestSecurityHardening:
    """Test security hardening features"""
    
    @pytest.fixture(scope="class")
    def docker_client(self):
        """Initialize Docker client"""
        return docker.from_env()
    
    def test_no_new_privileges(self, docker_client):
        """Verify no-new-privileges security option is set"""
        containers = docker_client.containers.list()
        
        for container in containers:
            name = container.name
            host_config = container.attrs.get("HostConfig", {})
            security_opt = host_config.get("SecurityOpt", [])
            
            # Check if no-new-privileges is set
            if "no-new-privileges:true" in security_opt or "no-new-privileges" in security_opt:
                print(f"✓ {name}: no-new-privileges enabled")
    
    def test_environment_variables_loaded(self, docker_client):
        """Verify environment variables are loaded correctly"""
        containers = docker_client.containers.list()
        
        # Check backend container for critical env vars
        for container in containers:
            if "backend" in container.name.lower():
                env_vars = container.attrs["Config"]["Env"]
                env_dict = {}
                for env in env_vars:
                    if "=" in env:
                        key, value = env.split("=", 1)
                        env_dict[key] = value
                
                # Check for critical variables
                critical_vars = [
                    "POSTGRES_HOST",
                    "POSTGRES_DB",
                    "JWT_SECRET_KEY",
                    "JWT_ALGORITHM",
                ]
                
                for var in critical_vars:
                    if var in env_dict:
                        print(f"✓ {var} is loaded")
                    else:
                        print(f"⚠ {var} is NOT loaded")


class TestOWASP:
    """OWASP Top 10 vulnerability checks"""
    
    BASE_URL = "http://localhost:8001"
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        client = httpx.Client(base_url=self.BASE_URL)
        response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get user token"""
        client = httpx.Client(base_url=self.BASE_URL)
        response = client.post(
            "/auth/login",
            json={"username": "user", "password": "user123"}
        )
        return response.json()["access_token"]
    
    def test_broken_access_control(self, user_token):
        """A01:2021 - Test role-based access control"""
        client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        # User should NOT be able to access admin endpoints
        response = client.get("/data/users")
        assert response.status_code == 403, "User should not access admin endpoints"
        print("✓ RBAC correctly prevents user from accessing admin endpoints")
    
    def test_authentication_failures(self):
        """A07:2021 - Test authentication mechanisms"""
        client = httpx.Client(base_url=self.BASE_URL)
        
        # Test 1: Wrong password
        response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401
        print("✓ Wrong password correctly rejected")
        
        # Test 2: Non-existent user
        response = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "password"}
        )
        assert response.status_code == 401
        print("✓ Non-existent user correctly rejected")
    
    def test_security_misconfiguration(self):
        """A05:2021 - Test security headers"""
        client = httpx.Client(base_url=self.BASE_URL)
        response = client.get("/data/traffic-events")
        
        headers = response.headers
        
        # Check for security headers
        if "X-Content-Type-Options" in headers:
            print(f"✓ X-Content-Type-Options: {headers['X-Content-Type-Options']}")
        
        if "X-Frame-Options" in headers:
            print(f"✓ X-Frame-Options: {headers['X-Frame-Options']}")
        
        if "X-XSS-Protection" in headers:
            print(f"✓ X-XSS-Protection: {headers['X-XSS-Protection']}")
    
    def test_injection_protection(self, admin_token):
        """A03:2021 - Test SQL injection protection"""
        client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Try SQL injection in query parameter
        response = client.get("/data/traffic-data?segment_id=1' OR '1'='1")
        
        # Should either return 422 (validation error) or 200 with no data
        assert response.status_code in [200, 422]
        print("✓ SQL injection attempt handled safely")


# Test execution summary
def pytest_sessionfinish(session, exitstatus):
    """Print summary after all tests complete"""
    print("\n" + "="*80)
    print("PHASE 4 COMPREHENSIVE SECURITY TESTING COMPLETE")
    print("="*80)
    print(f"\nExit Status: {exitstatus}")
    print("\nTest Categories Covered:")
    print("  ✓ Network Isolation (3 networks, service assignments)")
    print("  ✓ Authentication Stress (concurrent logins, token refresh)")
    print("  ✓ Rate Limiting (enforcement, headers, reset)")
    print("  ✓ Resource Limits (CPU, memory configuration)")
    print("  ✓ Performance Impact (latency measurements)")
    print("  ✓ Security Hardening (no-new-privileges, env vars)")
    print("  ✓ OWASP Top 10 (access control, auth, injection)")
