"""
Deployment script for FastAPI Traffic Prediction Backend
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path
import json
import time

# Configuration
DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "workers": 4,
    "reload": False,
    "log_level": "info",
    "access_log": True,
    "proxy_headers": True,
    "forwarded_allow_ips": "*"
}

PRODUCTION_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "workers": 8,
    "reload": False,
    "log_level": "info",
    "access_log": True,
    "proxy_headers": True,
    "forwarded_allow_ips": "*"
}

DEVELOPMENT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8000,
    "workers": 1,
    "reload": True,
    "log_level": "debug",
    "access_log": True,
    "proxy_headers": False,
    "forwarded_allow_ips": "127.0.0.1"
}


class DeploymentManager:
    """Manages FastAPI deployment"""
    
    def __init__(self, config_type="default"):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.api_root = Path(__file__).parent.parent
        self.config = self._get_config(config_type)
        
    def _get_config(self, config_type):
        """Get configuration based on type"""
        configs = {
            "default": DEFAULT_CONFIG,
            "production": PRODUCTION_CONFIG,
            "development": DEVELOPMENT_CONFIG
        }
        return configs.get(config_type, DEFAULT_CONFIG)
    
    def check_dependencies(self):
        """Check if all dependencies are installed"""
        print("Checking dependencies...")
        
        try:
            # Check if requirements file exists
            requirements_file = self.project_root / "requirements-fastapi.txt"
            if not requirements_file.exists():
                print("❌ requirements-fastapi.txt not found")
                return False
            
            # Try importing key dependencies
            import fastapi
            import uvicorn
            import sqlalchemy
            import psycopg2
            print("✅ Core dependencies available")
            
            return True
            
        except ImportError as e:
            print(f"❌ Missing dependency: {e}")
            return False
    
    def install_dependencies(self):
        """Install dependencies from requirements file"""
        print("Installing dependencies...")
        
        requirements_file = self.project_root / "requirements-fastapi.txt"
        if not requirements_file.exists():
            print("❌ requirements-fastapi.txt not found")
            return False
        
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Dependencies installed successfully")
            return True
        else:
            print(f"❌ Failed to install dependencies: {result.stderr}")
            return False
    
    def check_database_connection(self):
        """Check database connectivity"""
        print("Checking database connection...")
        
        try:
            # This would need the database configuration
            # For now, just check if PostgreSQL is available
            import psycopg2
            
            # Try to connect with default settings
            # In production, this would use actual config values
            connection_params = {
                "host": os.getenv("DB_HOST", "localhost"),
                "port": os.getenv("DB_PORT", "5432"),
                "database": os.getenv("DB_NAME", "traffic_db"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "password")
            }
            
            conn = psycopg2.connect(**connection_params)
            conn.close()
            print("✅ Database connection successful")
            return True
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def check_kafka_connection(self):
        """Check Kafka connectivity"""
        print("Checking Kafka connection...")
        
        try:
            from kafka import KafkaProducer
            
            producer = KafkaProducer(
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                value_serializer=lambda v: json.dumps(v).encode()
            )
            producer.close()
            print("✅ Kafka connection successful")
            return True
            
        except Exception as e:
            print(f"❌ Kafka connection failed: {e}")
            return False
    
    def setup_environment(self):
        """Setup environment variables"""
        print("Setting up environment...")
        
        # Default environment variables
        env_vars = {
            "PYTHONPATH": str(self.api_root),
            "FASTAPI_ENV": "production",
            "API_HOST": self.config["host"],
            "API_PORT": str(self.config["port"]),
            "LOG_LEVEL": self.config["log_level"].upper()
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
            print(f"Set {key}={value}")
        
        print("✅ Environment configured")
    
    def run_health_checks(self):
        """Run comprehensive health checks"""
        print("\nRunning health checks...")
        
        checks = [
            ("Dependencies", self.check_dependencies),
            ("Database", self.check_database_connection),
            ("Kafka", self.check_kafka_connection)
        ]
        
        results = {}
        for check_name, check_func in checks:
            try:
                results[check_name] = check_func()
            except Exception as e:
                print(f"❌ {check_name} check failed with exception: {e}")
                results[check_name] = False
        
        all_passed = all(results.values())
        print(f"\nHealth check summary:")
        for check_name, passed in results.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
        
        return all_passed
    
    def start_server(self, background=False):
        """Start the FastAPI server"""
        print(f"Starting FastAPI server...")
        print(f"Configuration: {self.config}")
        
        # Build uvicorn command
        cmd = [
            sys.executable, "-m", "uvicorn",
            "src.api.main:app",
            "--host", self.config["host"],
            "--port", str(self.config["port"]),
            "--workers", str(self.config["workers"]),
            "--log-level", self.config["log_level"]
        ]
        
        if self.config["reload"]:
            cmd.append("--reload")
        
        if self.config["access_log"]:
            cmd.append("--access-log")
        
        if self.config["proxy_headers"]:
            cmd.extend(["--proxy-headers"])
        
        cmd.extend(["--forwarded-allow-ips", self.config["forwarded_allow_ips"]])
        
        print(f"Command: {' '.join(cmd)}")
        
        if background:
            # Start in background
            process = subprocess.Popen(cmd, cwd=self.project_root)
            print(f"✅ Server started in background (PID: {process.pid})")
            return process
        else:
            # Start in foreground
            subprocess.run(cmd, cwd=self.project_root)
    
    def create_systemd_service(self, service_name="traffic-api"):
        """Create systemd service file for production deployment"""
        service_content = f"""[Unit]
Description=Traffic Prediction FastAPI Service
After=network.target postgresql.service kafka.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory={self.project_root}
Environment=PATH={self.project_root}/traffic_env/bin
Environment=PYTHONPATH={self.api_root}
Environment=FASTAPI_ENV=production
ExecStart={self.project_root}/traffic_env/bin/uvicorn src.api.main:app --host {self.config["host"]} --port {self.config["port"]} --workers {self.config["workers"]} --daemon
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        
        service_file = Path(f"/etc/systemd/system/{service_name}.service")
        try:
            with open(service_file, 'w') as f:
                f.write(service_content)
            print(f"✅ Systemd service file created: {service_file}")
            
            # Reload systemd and enable service
            subprocess.run(["sudo", "systemctl", "daemon-reload"])
            subprocess.run(["sudo", "systemctl", "enable", service_name])
            print(f"✅ Service {service_name} enabled")
            
        except PermissionError:
            print(f"❌ Permission denied. Run with sudo to create systemd service")
            print(f"Service content saved to: {service_name}.service")
            
            with open(f"{service_name}.service", 'w') as f:
                f.write(service_content)
    
    def create_nginx_config(self, domain="localhost"):
        """Create Nginx configuration for reverse proxy"""
        nginx_config = f"""server {{
    listen 80;
    server_name {domain};
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    location / {{
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://127.0.0.1:{self.config["port"]};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }}
    
    # WebSocket support
    location /ws/ {{
        proxy_pass http://127.0.0.1:{self.config["port"]};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    
    # Static files and API docs
    location /docs {{
        proxy_pass http://127.0.0.1:{self.config["port"]};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    
    location /redoc {{
        proxy_pass http://127.0.0.1:{self.config["port"]};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
        
        config_file = f"traffic-api-{domain}.conf"
        with open(config_file, 'w') as f:
            f.write(nginx_config)
        
        print(f"✅ Nginx configuration created: {config_file}")
        print(f"Copy to /etc/nginx/sites-available/ and enable with:")
        print(f"sudo cp {config_file} /etc/nginx/sites-available/")
        print(f"sudo ln -s /etc/nginx/sites-available/{config_file} /etc/nginx/sites-enabled/")
        print(f"sudo nginx -t && sudo systemctl reload nginx")


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(description="FastAPI Deployment Manager")
    parser.add_argument("--config", choices=["default", "production", "development"], 
                       default="default", help="Configuration type")
    parser.add_argument("--install-deps", action="store_true", help="Install dependencies")
    parser.add_argument("--health-check", action="store_true", help="Run health checks only")
    parser.add_argument("--background", action="store_true", help="Start server in background")
    parser.add_argument("--create-service", action="store_true", help="Create systemd service")
    parser.add_argument("--create-nginx", action="store_true", help="Create nginx config")
    parser.add_argument("--domain", default="localhost", help="Domain for nginx config")
    parser.add_argument("--service-name", default="traffic-api", help="Systemd service name")
    
    args = parser.parse_args()
    
    # Initialize deployment manager
    deploy = DeploymentManager(args.config)
    
    # Install dependencies if requested
    if args.install_deps:
        if not deploy.install_dependencies():
            sys.exit(1)
    
    # Run health checks
    if args.health_check:
        if deploy.run_health_checks():
            print("\n✅ All health checks passed!")
        else:
            print("\n❌ Some health checks failed!")
            sys.exit(1)
        return
    
    # Create systemd service
    if args.create_service:
        deploy.create_systemd_service(args.service_name)
        return
    
    # Create nginx config
    if args.create_nginx:
        deploy.create_nginx_config(args.domain)
        return
    
    # Setup environment and start server
    deploy.setup_environment()
    
    # Run health checks before starting
    if not deploy.run_health_checks():
        print("\nWarning: Some health checks failed. Continue anyway? (y/N)")
        if input().lower() != 'y':
            sys.exit(1)
    
    print(f"\n🚀 Starting FastAPI server with {args.config} configuration...")
    deploy.start_server(background=args.background)


if __name__ == "__main__":
    main()