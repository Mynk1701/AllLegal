"""
Authentication routes for user login and registration.
Integrates with Supabase authentication.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging
from app.schemas.schemas import LoginRequest, SignUpRequest, AuthResponse
from app.services.supabase import supabase_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest) -> AuthResponse:
    """
    🔐 Sign in existing user with email and password.
    
    Returns JWT access token for authenticated API requests.
    
    **Parameters:**
    - `email`: User email address
    - `password`: User password (min 6 characters)
    
    **Response:**
    JWT token to use in Authorization header: `Authorization: Bearer {token}`
    """
    try:
        logger.info(f"🔑 Login attempt for: {request.email}")
        
        result = supabase_service.sign_in(request.email, request.password)
        
        if not result:
            logger.warning(f"❌ Login failed for: {request.email}")
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        logger.info(f"✅ Login successful for: {request.email}")
        
        return AuthResponse(
            access_token=result["access_token"],
            user_id=result["user_id"],
            message="Login successful"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Authentication service error"
        )

@router.post("/auth/signup", response_model=AuthResponse)
async def signup(request: SignUpRequest) -> AuthResponse:
    """
    📝 Register a new user with email and password.
    
    Creates new user account in Supabase.
    
    **Parameters:**
    - `email`: User email address
    - `password`: User password (min 6 characters)
    
    **Response:**
    User ID and temporary token. User must verify email before full access.
    """
    try:
        logger.info(f"📝 Signup attempt for: {request.email}")
        
        # Check password minimum length
        if len(request.password) < 6:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 6 characters"
            )
        
        user_data = supabase_service.sign_up(request.email, request.password)
        
        if not user_data:
            logger.warning(f"❌ Signup failed for: {request.email}")
            raise HTTPException(
                status_code=400,
                detail="Email already exists or signup failed"
            )
        
        logger.info(f"✅ Signup successful for: {request.email}")
        
        return AuthResponse(
            access_token="",  # Temp token, user must verify email
            user_id=user_data.get("id", ""),
            message="Signup successful. Please verify your email."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Signup error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Authentication service error"
        )
