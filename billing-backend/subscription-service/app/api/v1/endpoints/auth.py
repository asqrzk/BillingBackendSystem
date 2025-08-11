from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.auth import AuthService, get_current_active_user
from app.core.config import settings
from app.schemas.auth import LoginRequest, TokenResponse, RegisterRequest, ChangePasswordRequest
from app.schemas.user import UserResponse
from app.repositories.user_repository import UserRepository
from app.models.user import User

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Authenticate user and return access token.
    
    - **email**: User email address
    - **password**: User password
    """
    user_repo = UserRepository(session)
    
    # Get user by email
    user = await user_repo.get_by_email(login_data.email)
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not AuthService.verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    register_data: RegisterRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Register a new user account.
    
    - **email**: User email address (must be unique)
    - **password**: User password
    - **first_name**: Optional first name
    - **last_name**: Optional last name
    """
    user_repo = UserRepository(session)
    
    # Check if user already exists
    existing_user = await user_repo.get_by_email(register_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user_data = {
        "email": register_data.email,
        "password_hash": AuthService.get_password_hash(register_data.password),
        "first_name": register_data.first_name,
        "last_name": register_data.last_name
    }
    
    user = await user_repo.create(user_data)
    await session.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current authenticated user information.
    """
    return UserResponse.from_orm(current_user)


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Change current user's password.
    
    - **current_password**: Current password for verification
    - **new_password**: New password
    """
    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password not set for this user"
        )
    
    # Verify current password
    if not AuthService.verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Update password
    user_repo = UserRepository(session)
    new_password_hash = AuthService.get_password_hash(password_data.new_password)
    await user_repo.update(current_user.id, {"password_hash": new_password_hash})
    await session.commit()
    
    return {"message": "Password changed successfully"}


@router.post("/refresh")
async def refresh_token(
    current_user: User = Depends(get_current_active_user)
):
    """
    Refresh access token for authenticated user.
    """
    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token(
        data={"sub": str(current_user.id)}, expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=current_user.id,
        email=current_user.email
    ) 