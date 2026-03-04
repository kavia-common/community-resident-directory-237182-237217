"""
Authentication routes: login, register, and user profile.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from datetime import timedelta
import logging

from src.models import LoginRequest, LoginResponse, RegisterRequest, SuccessResponse
from src.auth import (
    verify_password, create_access_token, hash_password,
    get_current_user, get_user_by_id
)
from src.database import get_db_connection, get_db_cursor
from src.config import settings
from src.audit import create_audit_log, get_client_ip, get_user_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse, summary="User login")
async def login(login_data: LoginRequest, request: Request):
    """
    Authenticate user and return JWT access token.
    
    - **email**: User email address
    - **password**: User password
    
    Returns JWT token and user information.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Get user by email
                cursor.execute("""
                    SELECT u.id, u.email, u.password_hash, u.role_id, r.name as role_name, u.is_active
                    FROM users u
                    LEFT JOIN roles r ON u.role_id = r.id
                    WHERE u.email = %s
                """, (login_data.email,))
                
                user = cursor.fetchone()
                
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password"
                    )
                
                if not user['is_active']:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account is inactive"
                    )
                
                # Verify password
                if not verify_password(login_data.password, user['password_hash']):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password"
                    )
                
                # Update last login
                cursor.execute("""
                    UPDATE users 
                    SET last_login = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user['id'],))
                
                # Create audit log
                create_audit_log(
                    user_id=user['id'],
                    action="user_login",
                    entity_type="user",
                    entity_id=user['id'],
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                # Create access token
                access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(
                    data={"sub": str(user['id']), "role": user['role_name']},
                    expires_delta=access_token_expires
                )
                
                # Get full user profile
                user_profile = get_user_by_id(user['id'])
                
                return LoginResponse(
                    access_token=access_token,
                    token_type="bearer",
                    user=dict(user_profile) if user_profile else {}
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/register", response_model=SuccessResponse, summary="Register new user")
async def register(register_data: RegisterRequest, request: Request):
    """
    Register a new user account with resident profile.
    
    - **email**: User email address (must be unique)
    - **password**: User password (min 6 characters)
    - **first_name**: User's first name
    - **last_name**: User's last name
    - **phone**: Optional phone number
    - **unit_number**: Optional unit number
    - **floor_number**: Optional floor number
    - **building**: Optional building name
    
    Returns success message with user ID.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Check if email already exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (register_data.email,))
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered"
                    )
                
                # Get resident role ID
                cursor.execute("SELECT id FROM roles WHERE name = 'resident'")
                role = cursor.fetchone()
                if not role:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Resident role not found"
                    )
                
                # Hash password
                hashed_password = hash_password(register_data.password)
                
                # Create user
                cursor.execute("""
                    INSERT INTO users (email, password_hash, role_id, is_active)
                    VALUES (%s, %s, %s, true)
                    RETURNING id
                """, (register_data.email, hashed_password, role['id']))
                
                user_result = cursor.fetchone()
                user_id = user_result['id']
                
                # Create resident profile
                cursor.execute("""
                    INSERT INTO resident_profiles 
                        (user_id, first_name, last_name, phone, unit_number, 
                         floor_number, building)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, register_data.first_name, register_data.last_name,
                      register_data.phone, register_data.unit_number,
                      register_data.floor_number, register_data.building))
                
                profile_result = cursor.fetchone()
                
                # Create audit log
                create_audit_log(
                    user_id=user_id,
                    action="user_registered",
                    entity_type="user",
                    entity_id=user_id,
                    details={"email": register_data.email},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="User registered successfully",
                    data={"user_id": user_id, "profile_id": profile_result['id']}
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.get("/me", summary="Get current user profile")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get the current authenticated user's profile.
    
    Requires authentication (Bearer token).
    
    Returns complete user profile including role and resident details.
    """
    return {
        "user": current_user
    }
