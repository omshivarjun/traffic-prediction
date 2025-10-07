# Security System Quick Reference Guide

## 🔐 Authentication Quick Start

### Default Test Accounts

**⚠️ CHANGE THESE IN PRODUCTION!**

| Username | Password | Role | Permissions |
|----------|----------|------|-------------|
| `admin` | `Admin@123456789` | admin | Full access |
| `user` | `User@123456789` | user | Read/write |
| `viewer` | `Viewer@123456789` | viewer | Read-only |

---

## 📡 API Endpoints

### Login (Get JWT Token)

**OAuth2 Compatible:**
```bash
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=Admin@123456789"
```

**JSON Format:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Admin@123456789"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### Use Token for Protected Requests

```bash
curl -X GET "http://localhost:8000/api/traffic/current" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Refresh Access Token

```bash
curl -X POST "http://localhost:8000/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

### Get Current User Info

```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Change Password

```bash
curl -X POST "http://localhost:8000/auth/change-password" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "Admin@123456789",
    "new_password": "NewSecure@Password123"
  }'
```

### Create New User (Admin Only)

```bash
curl -X POST "http://localhost:8000/auth/users" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "SecurePass@123",
    "full_name": "New User",
    "role": "user"
  }'
```

### List All Users (Admin Only)

```bash
curl -X GET "http://localhost:8000/auth/users" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

### Get Role Information

```bash
curl -X GET "http://localhost:8000/auth/roles" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 🔑 Password Requirements

All passwords must meet these criteria:

- ✅ Minimum 12 characters
- ✅ At least 1 uppercase letter (A-Z)
- ✅ At least 1 lowercase letter (a-z)
- ✅ At least 1 digit (0-9)
- ✅ At least 1 special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

**Valid Examples:**
- `MySecure@Password123`
- `Traffic$Prediction2024!`
- `Admin@P4ssw0rd!`

**Invalid Examples:**
- `short` ❌ (too short)
- `NoSpecialChar123` ❌ (no special character)
- `nouppercas@123` ❌ (no uppercase)
- `NOLOWERCASE@123` ❌ (no lowercase)
- `NoDigits@Here` ❌ (no numbers)

---

## 👥 Role Hierarchy

**Permissions flow from lower to higher:**

```
viewer (Level 1)
  ↓
user (Level 2)
  ↓
admin (Level 3)
```

**Access Control:**
- `viewer` can access viewer-level resources
- `user` can access viewer + user-level resources
- `admin` can access all resources

**Example:**
```python
# In your code
@router.get("/data", dependencies=[Depends(require_role("viewer"))])
async def get_data():
    # Accessible by viewer, user, and admin
    pass

@router.post("/data", dependencies=[Depends(require_role("user"))])
async def create_data():
    # Accessible by user and admin only
    pass

@router.delete("/data", dependencies=[Depends(require_role("admin"))])
async def delete_data():
    # Accessible by admin only
    pass
```

---

## 🛡️ Security Features

### Token Expiration

| Token Type | Expiration | Use Case |
|------------|-----------|----------|
| Access Token | 15 minutes | API requests |
| Refresh Token | 7 days | Token renewal |

**Best Practice:**
- Use access tokens for all API requests
- Store refresh token securely (HttpOnly cookie recommended)
- Implement token refresh before expiration

### Password Hashing

- Algorithm: bcrypt
- Automatic salt generation
- Configurable work factor
- Resistant to rainbow tables

### Rate Limiting (Coming in Phase 2)

| Tier | Per Minute | Per Hour |
|------|------------|----------|
| Default | 100 requests | 1,000 requests |
| Authenticated | 200 requests | 2,000 requests |
| Admin | Unlimited | Unlimited |

---

## 🐍 Python Client Example

```python
import requests
from typing import Optional

class TrafficAPIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
    
    def login(self, username: str, password: str) -> bool:
        """Login and store tokens"""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token")
            return True
        return False
    
    def get_headers(self) -> dict:
        """Get authorization headers"""
        if not self.access_token:
            raise ValueError("Not authenticated. Call login() first.")
        return {"Authorization": f"Bearer {self.access_token}"}
    
    def get_current_traffic(self):
        """Get current traffic data"""
        response = requests.get(
            f"{self.base_url}/api/traffic/current",
            headers=self.get_headers()
        )
        return response.json()
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token"""
        if not self.refresh_token:
            return False
        
        response = requests.post(
            f"{self.base_url}/auth/refresh",
            json={"refresh_token": self.refresh_token}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            return True
        return False

# Usage
client = TrafficAPIClient()
if client.login("admin", "Admin@123456789"):
    traffic_data = client.get_current_traffic()
    print(traffic_data)
```

---

## 🧪 Testing

### Run Security Tests

```bash
# All security tests
pytest tests/security/test_authentication.py -v

# Specific test class
pytest tests/security/test_authentication.py::TestPasswordHashing -v

# Specific test
pytest tests/security/test_authentication.py::TestPasswordHashing::test_password_verification_success -v
```

### Test Coverage

```bash
pytest tests/security/ --cov=src/api/security --cov=src/api/auth --cov-report=html
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file in project root:

```bash
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-min-32-characters-long
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:3002
```

### Generate Secure Secret Key

```bash
# Using OpenSSL
openssl rand -hex 32

# Using Python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🚨 Common Issues & Solutions

### Issue: "Could not validate credentials"

**Cause:** Invalid or expired token

**Solution:**
1. Check token is included in Authorization header
2. Verify token hasn't expired
3. Use refresh token to get new access token

### Issue: "Insufficient permissions"

**Cause:** User role doesn't have required permissions

**Solution:**
1. Check user role: `GET /auth/me`
2. Verify endpoint required role
3. Request admin to upgrade user role if needed

### Issue: "Incorrect username or password"

**Cause:** Invalid credentials

**Solution:**
1. Verify username and password are correct
2. Check password meets complexity requirements
3. Ensure account is not disabled

### Issue: Password validation fails

**Cause:** Password doesn't meet requirements

**Solution:**
Ensure password has:
- At least 12 characters
- Uppercase and lowercase letters
- At least one number
- At least one special character

---

## 📚 Additional Resources

**Documentation:**
- Full Implementation Plan: `docs/SECURITY_IMPLEMENTATION_PLAN.md`
- Progress Report: `docs/TODO_6_PROGRESS_REPORT.md`
- Environment Template: `.env.traffic.example`

**Source Code:**
- Security Module: `src/api/security.py`
- Auth Endpoints: `src/api/auth.py`
- Configuration: `src/api/config.py`

**Tests:**
- Security Tests: `tests/security/test_authentication.py`

---

**Last Updated:** October 5, 2025  
**Version:** 1.0.0  
**Status:** Phase 1 Complete - Ready for Integration
