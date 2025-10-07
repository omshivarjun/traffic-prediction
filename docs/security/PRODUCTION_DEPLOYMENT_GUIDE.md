# Phase 4: Production Deployment Guide

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Setup](#environment-setup)
3. [Security Configuration](#security-configuration)
4. [Network Hardening](#network-hardening)
5. [Deployment Steps](#deployment-steps)
6. [Post-Deployment Validation](#post-deployment-validation)
7. [Monitoring & Logging](#monitoring--logging)
8. [Rollback Procedures](#rollback-procedures)
9. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### Infrastructure Requirements
- [ ] **Server Resources**
  - [ ] 26+ CPU cores available
  - [ ] 32GB+ RAM available
  - [ ] 500GB+ disk space for HDFS
  - [ ] High-speed network connectivity (1Gbps+)

- [ ] **Software Prerequisites**
  - [ ] Docker Engine 24.0+ installed
  - [ ] Docker Compose v2.20+ installed
  - [ ] Git installed for version control
  - [ ] SSL certificates obtained (if using HTTPS)

- [ ] **Network Requirements**
  - [ ] Static IP address assigned
  - [ ] Firewall rules configured
  - [ ] DNS records created (if applicable)
  - [ ] Load balancer configured (if using)

### Security Prerequisites
- [ ] **Credentials Generated**
  - [ ] Strong PostgreSQL password (24+ characters)
  - [ ] JWT secret keys (256-bit random hex)
  - [ ] JWT refresh secret keys (256-bit random hex)
  - [ ] Hive metastore password
  - [ ] All credentials stored securely (e.g., HashiCorp Vault, AWS Secrets Manager)

- [ ] **SSL/TLS Certificates** (if enabling HTTPS)
  - [ ] Domain SSL certificate obtained
  - [ ] Certificate chain complete
  - [ ] Private key secured (600 permissions)
  - [ ] Certificate expiration monitoring configured

- [ ] **Access Control**
  - [ ] Admin users defined
  - [ ] Regular users defined
  - [ ] RBAC roles configured
  - [ ] API key management system in place

---

## Environment Setup

### Step 1: Clone Repository
```bash
# Production server
git clone https://github.com/your-org/traffic-prediction.git
cd traffic-prediction
git checkout main  # or specific release tag
```

### Step 2: Run Automated Security Setup
```powershell
# Windows
.\setup-security.ps1

# Or manually configure .env file
cp .env.template .env
# Edit .env with production values
```

### Step 3: Configure Production Environment Variables

**Required Changes in `.env`:**
```bash
# 1. Database (use strong production password)
POSTGRES_PASSWORD=<STRONG_PRODUCTION_PASSWORD>
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=traffic_db
POSTGRES_USER=postgres

# 2. JWT Authentication (generate new production secrets)
JWT_SECRET_KEY=<PRODUCTION_SECRET_256BIT_HEX>
JWT_REFRESH_SECRET_KEY=<PRODUCTION_REFRESH_SECRET_256BIT_HEX>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# 3. Security Settings
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
SESSION_COOKIE_SECURE=True  # MUST be True with HTTPS
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Strict  # Stricter in production

# 4. Kafka Security (if enabling SASL/SSL)
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=<KAFKA_USERNAME>
KAFKA_SASL_PASSWORD=<KAFKA_PASSWORD>

# 5. Hadoop Security
HIVE_METASTORE_PASSWORD=<PRODUCTION_HIVE_PASSWORD>
HDFS_NAMENODE_URL=hdfs://namenode:9000
HDFS_REPLICATION_FACTOR=3  # Higher for production
```

### Step 4: Create Docker Secrets (Production)
```powershell
# Create secrets directory
mkdir -p secrets

# Generate PostgreSQL password
echo "<STRONG_PRODUCTION_PASSWORD>" > secrets/postgres_password.txt

# Generate JWT secrets
echo "<PRODUCTION_SECRET_256BIT_HEX>" > secrets/jwt_secret_key.txt
echo "<PRODUCTION_REFRESH_SECRET_256BIT_HEX>" > secrets/jwt_refresh_secret_key.txt

# Secure permissions (Linux/macOS)
chmod 600 secrets/*.txt

# Windows (PowerShell as Administrator)
icacls secrets\*.txt /inheritance:r /grant:r "${env:USERNAME}:F"
```

---

## Security Configuration

### Step 1: Enable Internal Docker Networks

**Edit `docker-compose.security.yml`:**
```yaml
networks:
  backend:
    driver: bridge
    subnet: 172.26.0.0/24
    name: traffic-backend
    internal: true  # ← CHANGE TO TRUE

  hadoop:
    driver: bridge
    subnet: 172.27.0.0/24
    name: traffic-hadoop
    internal: true  # ← CHANGE TO TRUE
```

**Why?** This prevents backend and Hadoop services from accessing the internet, reducing attack surface.

### Step 2: Enable Read-Only Containers (Optional)

**Edit `docker-compose.security.yml` for backend:**
```yaml
services:
  backend:
    read_only: true  # Enable read-only filesystem
    tmpfs:
      - /tmp
      - /var/run
      - /var/cache
```

**Why?** Prevents runtime modifications to container filesystem.

### Step 3: Configure SSL/TLS for Backend API (Optional)

**Create nginx reverse proxy configuration:**
```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Add to docker-compose.security.yml:**
```yaml
services:
  nginx:
    image: nginx:alpine
    container_name: nginx-proxy
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    networks:
      - frontend
    depends_on:
      - backend
```

---

## Network Hardening

### Step 1: Configure Firewall Rules

**Linux (ufw):**
```bash
# Allow SSH (change port if non-standard)
sudo ufw allow 22/tcp

# Allow HTTPS (if using)
sudo ufw allow 443/tcp

# Allow HTTP (redirect to HTTPS)
sudo ufw allow 80/tcp

# Block all other incoming by default
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Enable firewall
sudo ufw enable
```

**Windows (PowerShell as Administrator):**
```powershell
# Allow HTTPS
New-NetFirewallRule -DisplayName "HTTPS Inbound" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow

# Allow HTTP (redirect to HTTPS)
New-NetFirewallRule -DisplayName "HTTP Inbound" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow

# Block all other ports (review existing rules)
```

### Step 2: Restrict Docker Network Access

**Create `/etc/docker/daemon.json` (Linux) or `C:\ProgramData\docker\config\daemon.json` (Windows):**
```json
{
  "icc": false,
  "userland-proxy": false,
  "iptables": true,
  "ip-forward": false
}
```

**Restart Docker:**
```bash
# Linux
sudo systemctl restart docker

# Windows
Restart-Service docker
```

---

## Deployment Steps

### Step 1: Deploy with Production Configuration
```bash
# Stop any existing containers
docker-compose down

# Deploy with security configuration
docker-compose -f docker-compose.yml -f docker-compose.security.yml up -d

# Verify all services started
docker-compose ps
```

### Step 2: Initialize Database
```bash
# Run database migrations
docker exec -it $(docker ps -qf "name=backend") python -m alembic upgrade head

# Create initial admin user
docker exec -it $(docker ps -qf "name=backend") python -m scripts.create_admin_user
```

### Step 3: Initialize Kafka Topics
```bash
# Run Kafka topic creation script
docker exec -it $(docker ps -qf "name=kafka") /bin/bash
kafka-topics.sh --create --topic traffic-events --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.sh --create --topic processed-traffic-aggregates --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.sh --create --topic traffic-predictions --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.sh --create --topic traffic-alerts --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

### Step 4: Initialize HDFS Directories
```bash
# Create HDFS directories
docker exec -it $(docker ps -qf "name=namenode") /bin/bash
hdfs dfs -mkdir -p /traffic-data/raw
hdfs dfs -mkdir -p /traffic-data/processed
hdfs dfs -mkdir -p /models
hdfs dfs -chmod 755 /traffic-data
```

---

## Post-Deployment Validation

### Step 1: Health Checks

**Check all containers are running:**
```bash
docker-compose ps

# Expected: All services "Up" status
```

**Check service health:**
```bash
# Backend API
curl https://api.yourdomain.com/health

# Kafka
docker exec -it $(docker ps -qf "name=kafka") kafka-broker-api-versions.sh --bootstrap-server localhost:9092

# HDFS
docker exec -it $(docker ps -qf "name=namenode") hdfs dfsadmin -report
```

### Step 2: Security Validation

**Test authentication:**
```bash
# Should require authentication
curl -X GET https://api.yourdomain.com/data/traffic-data
# Expected: 401 Unauthorized

# Login and get token
curl -X POST https://api.yourdomain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_admin_password"}'

# Use token to access protected endpoint
curl -X GET https://api.yourdomain.com/data/traffic-data \
  -H "Authorization: Bearer <TOKEN>"
# Expected: 200 OK
```

**Test rate limiting:**
```bash
# Make 25 requests quickly
for i in {1..25}; do
  curl -X GET https://api.yourdomain.com/data/traffic-events
done
# Expected: First 20 succeed, last 5 return 429 Too Many Requests
```

**Test network isolation:**
```bash
# Backend should NOT be accessible directly
curl http://172.26.0.3:8000
# Expected: Timeout or connection refused

# Only accessible via frontend network (nginx/load balancer)
```

### Step 3: Performance Validation

**Run load test:**
```bash
# Using Apache Bench
ab -n 1000 -c 10 https://api.yourdomain.com/data/traffic-events

# Check:
# - Requests per second > 50
# - Average response time < 500ms
# - No failed requests
```

### Step 4: Monitoring Setup

**Configure Prometheus (optional):**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']
  
  - job_name: 'docker'
    static_configs:
      - targets: ['localhost:9323']
```

**Configure Grafana dashboards:**
- Docker container metrics
- API response times
- Rate limiting statistics
- Authentication attempts

---

## Monitoring & Logging

### Step 1: Centralized Logging

**Configure ELK Stack (Elasticsearch, Logstash, Kibana):**
```yaml
# docker-compose.logging.yml
services:
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
    volumes:
      - es-data:/usr/share/elasticsearch/data
  
  logstash:
    image: logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch
  
  kibana:
    image: kibana:8.11.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

**Configure Docker logging driver:**
```json
// /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### Step 2: Application Monitoring

**Key metrics to monitor:**
- **API Metrics:**
  - Request rate (requests/second)
  - Response time (p50, p95, p99)
  - Error rate (%)
  - Authentication success/failure rate

- **System Metrics:**
  - CPU usage per container
  - Memory usage per container
  - Disk I/O (HDFS)
  - Network throughput (Kafka)

- **Security Metrics:**
  - Failed login attempts
  - Rate limit hits
  - Token refresh rate
  - RBAC denial count

### Step 3: Alerting

**Configure alerts for:**
- [ ] Container down/unhealthy
- [ ] High error rate (>5%)
- [ ] High response time (>1000ms)
- [ ] Disk usage >80%
- [ ] Memory usage >90%
- [ ] Suspicious authentication patterns
- [ ] SSL certificate expiration (<30 days)

---

## Rollback Procedures

### Emergency Rollback Steps

**1. Identify Issue:**
```bash
# Check logs
docker-compose logs -f --tail=100

# Check container status
docker-compose ps

# Check resource usage
docker stats
```

**2. Quick Rollback:**
```bash
# Stop current deployment
docker-compose down

# Checkout previous version
git checkout <previous-tag>

# Redeploy
docker-compose -f docker-compose.yml -f docker-compose.security.yml up -d
```

**3. Database Rollback:**
```bash
# Downgrade database migrations
docker exec -it $(docker ps -qf "name=backend") python -m alembic downgrade <revision>
```

**4. Verify Rollback:**
```bash
# Check all services
docker-compose ps

# Test critical endpoints
curl https://api.yourdomain.com/health
```

---

## Troubleshooting

### Issue 1: Containers Won't Start

**Symptoms:**
- `docker-compose ps` shows "Exited" or "Restarting" status
- Services fail health checks

**Solutions:**
```bash
# Check logs
docker-compose logs <service-name>

# Check resource availability
docker stats

# Check network connectivity
docker network ls
docker network inspect traffic-backend

# Restart specific service
docker-compose restart <service-name>
```

### Issue 2: Authentication Not Working

**Symptoms:**
- All authenticated requests return 401
- JWT token validation fails

**Solutions:**
```bash
# Verify JWT secrets are loaded
docker exec -it $(docker ps -qf "name=backend") env | grep JWT

# Check .env file
cat .env | grep JWT

# Verify Docker secrets (if using)
docker exec -it $(docker ps -qf "name=backend") cat /run/secrets/jwt_secret_key

# Restart backend
docker-compose restart backend
```

### Issue 3: Rate Limiting Too Aggressive

**Symptoms:**
- Legitimate requests being blocked with 429
- Rate limit headers show very low limits

**Solutions:**
```bash
# Check current settings
cat .env | grep RATE_LIMIT

# Increase limits in .env
RATE_LIMIT_PER_MINUTE=200
RATE_LIMIT_PER_HOUR=2000

# Restart backend
docker-compose restart backend
```

### Issue 4: Network Isolation Blocking Required Traffic

**Symptoms:**
- Services can't communicate with each other
- External API calls failing from containers

**Solutions:**
```bash
# Temporarily disable internal networks for debugging
# Edit docker-compose.security.yml:
# Change internal: true to internal: false

# Restart affected services
docker-compose up -d

# Check connectivity
docker exec -it $(docker ps -qf "name=backend") ping postgres
docker exec -it $(docker ps -qf "name=backend") ping kafka

# If external API calls needed, add to specific services:
# Add to docker-compose.security.yml:
services:
  backend:
    networks:
      - frontend  # Has internet access
      - backend
```

### Issue 5: Resource Limits Causing OOM

**Symptoms:**
- Containers being killed unexpectedly
- "OOMKilled" in container status

**Solutions:**
```bash
# Check current memory usage
docker stats

# Increase memory limits in docker-compose.security.yml:
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 4G  # Increase from 2G

# Restart services
docker-compose up -d
```

---

## Production Deployment Checklist

### Pre-Deployment
- [ ] All infrastructure requirements met
- [ ] SSL certificates obtained and configured
- [ ] Production credentials generated securely
- [ ] `.env` file configured for production
- [ ] Docker secrets created
- [ ] Firewall rules configured
- [ ] DNS records created
- [ ] Load balancer configured (if using)

### Deployment
- [ ] Repository cloned and correct version checked out
- [ ] `docker-compose.security.yml` configured for production
- [ ] Internal networks enabled (`internal: true`)
- [ ] All containers started successfully
- [ ] Database migrations applied
- [ ] Initial admin user created
- [ ] Kafka topics created
- [ ] HDFS directories initialized

### Post-Deployment
- [ ] All health checks passing
- [ ] Authentication working correctly
- [ ] Rate limiting enforced
- [ ] Network isolation verified
- [ ] Performance benchmarks met
- [ ] Monitoring configured
- [ ] Logging configured
- [ ] Alerting configured
- [ ] Backup procedures established
- [ ] Rollback tested

### Documentation
- [ ] Production configuration documented
- [ ] Admin credentials securely stored
- [ ] Monitoring dashboards created
- [ ] Runbooks created for common issues
- [ ] Team trained on deployment procedures

---

## Next Steps

1. **Review this guide** with your DevOps team
2. **Test deployment** in staging environment first
3. **Schedule production deployment** during low-traffic period
4. **Monitor closely** for first 24-48 hours
5. **Conduct post-deployment review** after 1 week

---

## Support & Resources

- **Documentation:** `docs/security/`
- **Phase 3 Details:** `docs/security/PHASE3_NETWORK_SECURITY.md`
- **Setup Guide:** `docs/security/SECURITY_SETUP.md`
- **Test Results:** `docs/security/test-reports/`

For issues or questions, contact the security team or create an issue in the project repository.
