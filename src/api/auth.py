"""
Authentication Endpoints
Provides login, token refresh, and user management endpoints
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError

from .security import (
    Token, TokenData, User, UserInDB, UserCreate, UserLogin, PasswordChange,
    SecurityUtils, UserRepository, authenticate_user, ROLE_HIERARCHY
)
from .config import get_settings
from .logging_config import api_logger

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """
    Get current user from JWT token
    
    Args:
        token: JWT access token
    
    Returns:
        Current user object
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = SecurityUtils.decode_token(token)
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "access":
            raise credentials_exception
        
        token_data = TokenData(username=username, user_id=user_id)
    except JWTError:
        raise credentials_exception
    
    user = UserRepository.get_user_by_username(username=token_data.username)
    if user is None:
        raise credentials_exception
    
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Convert UserInDB to User (remove password hash)
    return User(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        disabled=user.disabled,
        created_at=user.created_at
    )


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get current active (non-disabled) user
    
    Args:
        current_user: Current user from token
    
    Returns:
        Current user if active
    
    Raises:
        HTTPException: If user is disabled
    """
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_role(required_role: str):
    """
    Dependency to require specific role or higher
    
    Args:
        required_role: Minimum required role (viewer, user, admin)
    
    Returns:
        Dependency function
    """
    async def role_checker(current_user: Annotated[User, Depends(get_current_active_user)]) -> User:
        if not SecurityUtils.check_role_permission(current_user.role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role} or higher"
            )
        return current_user
    return role_checker


@router.post("/token", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    OAuth2 compatible token login
    
    Args:
        form_data: OAuth2 password request form (username, password)
    
    Returns:
        Access and refresh tokens
    
    Raises:
        HTTPException: If authentication fails
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        api_logger.warning(f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = SecurityUtils.create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token_expires = timedelta(days=settings.jwt_refresh_token_expire_days)
    refresh_token = SecurityUtils.create_refresh_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=refresh_token_expires
    )
    
    api_logger.info(f"Successful login for user: {user.username}")
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/login", response_model=Token)
async def login_json(login_data: UserLogin):
    """
    JSON-based login endpoint
    
    Args:
        login_data: User login credentials
    
    Returns:
        Access and refresh tokens
    """
    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        api_logger.warning(f"Failed login attempt for username: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = SecurityUtils.create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires
    )
    
    refresh_token_expires = timedelta(days=settings.jwt_refresh_token_expire_days)
    refresh_token = SecurityUtils.create_refresh_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=refresh_token_expires
    )
    
    api_logger.info(f"Successful login for user: {user.username}")
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token
    
    Args:
        refresh_token: JWT refresh token
    
    Returns:
        New access token
    
    Raises:
        HTTPException: If refresh token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token"
    )
    
    try:
        payload = SecurityUtils.decode_token(refresh_token)
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "refresh":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = UserRepository.get_user_by_username(username)
    if user is None or user.disabled:
        raise credentials_exception
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = SecurityUtils.create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires
    )
    
    api_logger.info(f"Token refreshed for user: {user.username}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.get("/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    Get current user information
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        Current user object
    """
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Change user password
    
    Args:
        password_data: Old and new password
        current_user: Current authenticated user
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If old password is incorrect
    """
    # Verify old password
    user_db = UserRepository.get_user_by_username(current_user.username)
    if not SecurityUtils.verify_password(password_data.old_password, user_db.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )
    
    # Update password
    UserRepository.update_password(current_user.username, password_data.new_password)
    
    api_logger.info(f"Password changed for user: {current_user.username}")
    
    return {"message": "Password updated successfully"}


@router.post("/users", response_model=User, dependencies=[Depends(require_role("admin"))])
async def create_user(user: UserCreate):
    """
    Create a new user (admin only)
    
    Args:
        user: User creation data
    
    Returns:
        Created user object
    
    Raises:
        HTTPException: If username already exists
    """
    # Check if username already exists
    if UserRepository.get_user_by_username(user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create user
    db_user = UserRepository.create_user(user)
    
    api_logger.info(f"New user created: {user.username} with role: {user.role}")
    
    # Return User without password
    return User(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        full_name=db_user.full_name,
        role=db_user.role,
        disabled=db_user.disabled,
        created_at=db_user.created_at
    )


@router.get("/users", response_model=list[User], dependencies=[Depends(require_role("admin"))])
async def list_users():
    """
    List all users (admin only)
    
    Returns:
        List of all users
    """
    return UserRepository.list_users()


@router.get("/roles", response_model=dict)
async def list_roles(current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    List available roles and their hierarchy
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        Dictionary of roles and their permission levels
    """
    return {
        "roles": ROLE_HIERARCHY,
        "current_user_role": current_user.role,
        "current_user_level": ROLE_HIERARCHY[current_user.role]
    }
