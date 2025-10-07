"""
JWT Authentication and Security Module
Implements token-based authentication with role-based access control
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator
import secrets

from .config import get_settings

settings = get_settings()

# Password hashing context using bcrypt
# truncate_error=False to handle bcrypt's 72-byte limit automatically
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__default_rounds=12,
    bcrypt__truncate_error=False  # Auto-truncate long passwords instead of error
)


class Token(BaseModel):
    """JWT token response model"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenData(BaseModel):
    """Token payload data"""
    username: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = "viewer"
    scopes: list[str] = []


class User(BaseModel):
    """User model"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str = "viewer"
    disabled: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True


class UserInDB(User):
    """User model with hashed password"""
    hashed_password: str


class UserCreate(BaseModel):
    """User creation model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    password: str = Field(..., min_length=12)
    full_name: Optional[str] = None
    role: str = "viewer"
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password complexity"""
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserLogin(BaseModel):
    """User login model"""
    username: str
    password: str


class PasswordChange(BaseModel):
    """Password change model"""
    old_password: str
    new_password: str = Field(..., min_length=12)
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        """Validate password complexity"""
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


# Role hierarchy (higher values have more permissions)
ROLE_HIERARCHY = {
    "viewer": 1,
    "user": 2,
    "admin": 3
}


class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate password hash"""
        return pwd_context.hash(password)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token
        
        Args:
            data: Token payload data
            expires_delta: Token expiration time (default: 15 minutes)
        
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT refresh token
        
        Args:
            data: Token payload data
            expires_delta: Token expiration time (default: 7 days)
        
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and verify JWT token
        
        Args:
            token: Encoded JWT token
        
        Returns:
            Decoded token payload
        
        Raises:
            JWTError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm]
            )
            return payload
        except JWTError as e:
            raise JWTError(f"Could not validate credentials: {str(e)}")
    
    @staticmethod
    def check_role_permission(user_role: str, required_role: str) -> bool:
        """
        Check if user role has sufficient permissions
        
        Args:
            user_role: User's current role
            required_role: Required role for the operation
        
        Returns:
            True if user has sufficient permissions, False otherwise
        """
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 999)
        return user_level >= required_level


# In-memory user store (replace with database in production)
# This is just for demonstration - use proper database in production
USERS_DB: Dict[str, UserInDB] = {}

def _initialize_default_users():
    """Initialize default users (called lazily on first access)"""
    if not USERS_DB:  # Only initialize if empty
        USERS_DB["admin"] = UserInDB(
            id="1",
            username="admin",
            email="admin@traffic-prediction.com",
            full_name="System Administrator",
            role="admin",
            hashed_password=SecurityUtils.get_password_hash("Admin@Pass123!"),
            disabled=False,
            created_at=datetime.utcnow()
        )
        USERS_DB["user"] = UserInDB(
            id="2",
            username="user",
            email="user@traffic-prediction.com",
            full_name="Regular User",
            role="user",
            hashed_password=SecurityUtils.get_password_hash("User@Pass123!"),
            disabled=False,
            created_at=datetime.utcnow()
        )
        USERS_DB["viewer"] = UserInDB(
            id="3",
            username="viewer",
            email="viewer@traffic-prediction.com",
            full_name="Read Only Viewer",
            role="viewer",
            hashed_password=SecurityUtils.get_password_hash("Viewer@Pass123!"),
            disabled=False,
            created_at=datetime.utcnow()
        )


class UserRepository:
    """User repository for database operations"""
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[UserInDB]:
        """Get user by username"""
        _initialize_default_users()  # Ensure default users exist
        return USERS_DB.get(username)
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[UserInDB]:
        """Get user by ID"""
        _initialize_default_users()  # Ensure default users exist
        for user in USERS_DB.values():
            if user.id == user_id:
                return user
        return None
    
    @staticmethod
    def create_user(user: UserCreate) -> UserInDB:
        """Create a new user"""
        _initialize_default_users()  # Ensure default users exist
        user_id = str(len(USERS_DB) + 1)
        hashed_password = SecurityUtils.get_password_hash(user.password)
        
        db_user = UserInDB(
            id=user_id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            hashed_password=hashed_password,
            disabled=False
        )
        
        USERS_DB[user.username] = db_user
        return db_user
    
    @staticmethod
    def update_password(username: str, new_password: str) -> bool:
        """Update user password"""
        user = USERS_DB.get(username)
        if user:
            user.hashed_password = SecurityUtils.get_password_hash(new_password)
            return True
        return False
    
    @staticmethod
    def list_users() -> list[User]:
        """List all users (without passwords)"""
        return [
            User(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                disabled=user.disabled,
                created_at=user.created_at
            )
            for user in USERS_DB.values()
        ]


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """
    Authenticate user with username and password
    
    Args:
        username: Username
        password: Plain text password
    
    Returns:
        User object if authentication successful, None otherwise
    """
    user = UserRepository.get_user_by_username(username)
    if not user:
        return None
    if not SecurityUtils.verify_password(password, user.hashed_password):
        return None
    if user.disabled:
        return None
    return user
