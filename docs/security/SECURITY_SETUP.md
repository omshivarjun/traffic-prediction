# Security Setup Guide

This guide provides step-by-step instructions for implementing the Phase 3 security enhancements in the Traffic Prediction System.

---

## Quick Start (Development)

```powershell
# 1. Run automated security setup script
.\setup-security.ps1

# 2. Start services with security overlay
docker-compose -f docker-compose.yml -f docker-compose.security.yml up -d

# 3. Verify network isolation
docker network ls | grep traffic

# 4. Check backend logs
docker-compose logs -f backend
```

---

## Manual Setup

### 1. Environment Configuration

**Copy the environment template:**

```powershell
Copy-Item .env.template .env
```

**Generate JWT secrets:**

```powershell
# Option A: Using OpenSSL (if available)
openssl rand -hex 32  # For JWT_SECRET_KEY
openssl rand -hex 32  # For JWT_REFRESH_SECRET_KEY

# Option B: Using PowerShell
Add-Type -AssemblyName System.Security
$rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::new()
$bytes = New-Object byte[] 32
$rng.GetBytes($bytes)
[System.BitConverter]::ToString($bytes).Replace("-", "").ToLower()
```

**Update .env with generated secrets:**

```bash
# .env
JWT_SECRET_KEY=your_generated_secret_from_above
JWT_REFRESH_SECRET_KEY=your_other_generated_secret
```

### 2. Generate Strong Passwords

**PostgreSQL password:**

```powershell
# Generate random password (24 characters)
-join ((48..57) + (65..90) + (97..122) + (33,35,36,37,38,42,43,45,61) | Get-Random -Count 24 | ForEach-Object {[char]$_})
```

**Update all PostgreSQL references in .env:**

```bash
POSTGRES_PASSWORD=your_strong_password

# Update connection URLs
DATABASE_URL=postgresql://postgres:your_strong_password@postgres:5432/traffic_db
ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:your_strong_password@postgres:5432/traffic_db
```

### 3. Docker Secrets (Production)

**Create secrets directory:**

```powershell
mkdir secrets
```

**Create secret files:**

```powershell
# PostgreSQL password
echo "your_strong_password" | Out-File -FilePath secrets\postgres_password.txt -NoNewline

# JWT secrets
echo "your_jwt_secret_key" | Out-File -FilePath secrets\jwt_secret_key.txt -NoNewline
echo "your_jwt_refresh_key" | Out-File -FilePath secrets\jwt_refresh_secret_key.txt -NoNewline

# Secure permissions (PowerShell - restrict to current user)
$acl = Get-Acl secrets
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule($env:USERNAME, "FullControl", "Allow")
$acl.SetAccessRule($rule)
Set-Acl secrets $acl
```

### 4. Network Isolation

The `docker-compose.security.yml` file defines three isolated networks:

- **frontend** (172.25.0.0/24) - Public-facing services
- **backend** (172.26.0.0/24) - Internal data services  
- **hadoop** (172.27.0.0/24) - Big data processing

**Start with security overlay:**

```powershell
docker-compose -f docker-compose.yml -f docker-compose.security.yml up -d
```

**Verify networks:**

```powershell
docker network ls | Select-String "traffic"
# Should show: traffic-frontend, traffic-backend, traffic-hadoop

docker network inspect traffic-backend
```

---

## Production Deployment

### 1. Production Environment Variables

Update `.env` for production:

```bash
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=WARNING
SESSION_COOKIE_SECURE=True  # Requires HTTPS
```

### 2. Enable Internal Networks

Edit `docker-compose.security.yml`:

```yaml
networks:
  backend:
    internal: true  # Block external access
  hadoop:
    internal: true  # Block external access
```

### 3. CORS Configuration

Update allowed origins:

```bash
CORS_ORIGINS=https://your-production-domain.com,https://api.your-domain.com
```

### 4. Kafka Security (Optional)

For production, enable Kafka SASL/SSL:

```bash
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=your_kafka_username
KAFKA_SASL_PASSWORD=your_kafka_password
```

### 5. PostgreSQL SSL/TLS (Optional)

See `docs/security/PHASE3_NETWORK_SECURITY.md` for SSL certificate generation and configuration.

---

## Verification Tests

### Test 1: Environment Variables Loaded

```powershell
docker-compose -f docker-compose.yml -f docker-compose.security.yml config | Select-String "POSTGRES_PASSWORD"
```

Should show password from `.env` (not hardcoded).

### Test 2: Network Isolation

```powershell
# Backend cannot access external network (when internal: true)
docker exec -it postgres-traffic ping 8.8.8.8
# Should fail if backend network is internal

# Backend can access other backend services
docker exec -it postgres-traffic ping kafka-broker1
# Should succeed
```

### Test 3: Service Connectivity

```powershell
# Backend can connect to PostgreSQL
docker-compose logs backend | Select-String "Database connection"

# Backend can connect to Kafka
docker-compose logs backend | Select-String "Kafka"
```

### Test 4: Resource Limits

```powershell
docker stats backend --no-stream
# Should show CPU/memory usage constrained by limits
```

### Test 5: Security Headers

```powershell
# Test API security headers
curl -I http://localhost:8000/health

# Should include:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
```

---

## Troubleshooting

### Issue: Services Can't Communicate

**Symptom:** Backend can't connect to PostgreSQL or Kafka

**Solution:**
1. Check network assignments in logs:
   ```powershell
   docker inspect backend | Select-String -Pattern "Networks" -Context 0,10
   ```

2. Verify services are on same network:
   ```powershell
   docker network inspect traffic-backend
   ```

3. Test connectivity:
   ```powershell
   docker exec -it backend ping postgres
   docker exec -it backend ping kafka-broker1
   ```

### Issue: Environment Variables Not Loading

**Symptom:** Services using default/hardcoded values

**Solution:**
1. Verify .env file exists:
   ```powershell
   Test-Path .env
   ```

2. Check docker-compose reads .env:
   ```powershell
   docker-compose -f docker-compose.yml -f docker-compose.security.yml config
   ```

3. Restart services to reload .env:
   ```powershell
   docker-compose -f docker-compose.yml -f docker-compose.security.yml down
   docker-compose -f docker-compose.yml -f docker-compose.security.yml up -d
   ```

### Issue: Resource Limits Too Restrictive

**Symptom:** Services crashing or OOM (Out of Memory)

**Solution:**

Edit `docker-compose.security.yml` and increase limits:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '4.0'    # Increase from 2.0
          memory: 4G     # Increase from 2G
```

### Issue: Docker Secrets Not Working

**Symptom:** Services can't read `/run/secrets/...`

**Solution:**

1. Verify secrets files exist:
   ```powershell
   Get-ChildItem secrets\
   ```

2. Check secrets are defined in docker-compose.security.yml:
   ```yaml
   secrets:
     postgres_password:
       file: ./secrets/postgres_password.txt
   ```

3. Verify service has secrets assigned:
   ```yaml
   services:
     backend:
       secrets:
         - postgres_password
   ```

---

## Security Checklist

### Development Environment
- [x] .env created from template
- [x] JWT secrets generated
- [x] Strong PostgreSQL password set
- [x] .env added to .gitignore
- [x] Network isolation enabled
- [x] Resource limits applied

### Production Environment
- [ ] All passwords 16+ characters
- [ ] JWT secrets generated with cryptographic RNG
- [ ] ENVIRONMENT=production
- [ ] DEBUG=False
- [ ] LOG_LEVEL=WARNING or ERROR
- [ ] SESSION_COOKIE_SECURE=True (requires HTTPS)
- [ ] CORS_ORIGINS updated to production domains
- [ ] Backend network internal: true
- [ ] Hadoop network internal: true
- [ ] Docker secrets configured
- [ ] PostgreSQL SSL/TLS enabled (optional)
- [ ] Kafka SASL/SSL enabled (optional)
- [ ] API HTTPS configured
- [ ] Monitoring and logging configured
- [ ] Backup strategy implemented
- [ ] Disaster recovery tested

---

## File Structure

```
traffic-prediction/
├── .env                          # Environment variables (gitignored)
├── .env.template                 # Template for .env (committed)
├── .gitignore                    # Protects .env, secrets/
├── docker-compose.yml            # Base configuration
├── docker-compose.security.yml   # Security overlay
├── setup-security.ps1            # Automated setup script
├── secrets/                      # Docker secrets (gitignored)
│   ├── postgres_password.txt
│   ├── jwt_secret_key.txt
│   └── jwt_refresh_secret_key.txt
└── docs/
    └── security/
        ├── PHASE3_NETWORK_SECURITY.md
        └── SECURITY_SETUP.md (this file)
```

---

## Additional Resources

- **Phase 3 Documentation:** `docs/security/PHASE3_NETWORK_SECURITY.md`
- **Docker Networks:** https://docs.docker.com/network/
- **Docker Secrets:** https://docs.docker.com/engine/swarm/secrets/
- **Environment Best Practices:** https://12factor.net/config
- **PostgreSQL Security:** https://www.postgresql.org/docs/current/auth-pg-hba-conf.html
- **Kafka Security:** https://kafka.apache.org/documentation/#security

---

## Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs -f backend`
2. Verify configuration: `docker-compose config`
3. Review network setup: `docker network inspect traffic-backend`
4. Test connectivity: `docker exec -it backend ping postgres`
5. Consult documentation: `docs/security/PHASE3_NETWORK_SECURITY.md`

---

**Last Updated:** January 2025  
**Phase:** 3 - Encryption & Network Security
