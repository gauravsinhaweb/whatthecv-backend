from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Any
import secrets

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserResponse, UserOTP, OTPVerify
from app.services.auth import authenticate_user, create_user, create_otp, verify_otp, get_current_user
from app.utils.google import get_google_auth_url, exchange_code_for_token, get_google_user_info
from app.utils.supabase import (
    sign_out_supabase_user,
    reset_password_supabase,
    google_sign_in_supabase
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=UserResponse)
async def signup(user_data: UserCreate, db: Session = Depends(get_db)) -> Any:
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        if not existing_user.is_verified:
            await create_otp(db, user_data.email, "signup")
            return existing_user
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
    
    user, supabase_result = await create_user(db, user_data)
    
    if supabase_result.get("error"):
        # Log Supabase error but continue with local auth
        print(f"Supabase signup error: {supabase_result['error']}")
    
    await create_otp(db, user_data.email, "signup")
    
    return user

@router.post("/signup/verify", response_model=Token)
async def verify_signup(verify_data: OTPVerify, db: Session = Depends(get_db)) -> Any:
    user = db.query(User).filter(User.email == verify_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already verified",
        )
    
    if await verify_otp(db, verify_data.email, verify_data.code, "signup"):
        user.is_verified = True
        db.commit()
        access_token = create_access_token(user.id)
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code",
        )

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Any:
    user, auth_result = await authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=auth_result.get("error", "Authentication failed"),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified",
        )
    
    access_token = create_access_token(user.id)
    
    # If Supabase authentication failed but local auth succeeded, log the error
    if auth_result.get("error") and user.supabase_id:
        print(f"Supabase login error: {auth_result['error']}")
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(response: Response, token: str = Depends(get_current_user)) -> Any:
    try:
        # Attempt to sign out from Supabase too
        await sign_out_supabase_user(token)
    except Exception as e:
        # Just log errors but don't fail if Supabase logout fails
        print(f"Supabase logout error: {str(e)}")
    
    # Clear cookies if any
    response.delete_cookie(key="access_token")
    return {"detail": "Successfully logged out"}

@router.post("/otp/request")
async def request_otp(user_data: UserOTP, purpose: str = "login", db: Session = Depends(get_db)) -> Any:
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user and purpose != "signup":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    await create_otp(db, user_data.email, purpose)
    return {"message": "OTP sent successfully"}

@router.post("/otp/login", response_model=Token)
async def otp_login(verify_data: OTPVerify, db: Session = Depends(get_db)) -> Any:
    user = db.query(User).filter(User.email == verify_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified",
        )
    
    if await verify_otp(db, verify_data.email, verify_data.code, "login"):
        access_token = create_access_token(user.id)
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code",
        )

@router.post("/password/reset")
async def reset_password(user_data: UserOTP) -> Any:
    try:
        await reset_password_supabase(user_data.email)
        return {"message": "Password reset email sent"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send reset email: {str(e)}",
        )

@router.get("/google")
async def google_login() -> Any:
    try:
        # Try Supabase OAuth first
        supabase_oauth = await google_sign_in_supabase()
        return RedirectResponse(supabase_oauth.url)
    except Exception:
        # Fall back to custom Google OAuth
        redirect_url = get_google_auth_url()
        return RedirectResponse(redirect_url)

@router.get("/google/callback")
async def google_callback(code: str, request: Request, db: Session = Depends(get_db)) -> Any:
    token_data = await exchange_code_for_token(code)
    id_token = token_data.get("id_token")
    
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to verify Google authentication",
        )
    
    user_info = await get_google_user_info(id_token)
    email = user_info.get("email")
    google_id = user_info.get("sub")
    
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        user_data = UserCreate(email=email)
        user, _ = await create_user(db, user_data)
        user.is_verified = True
        user.google_id = google_id
        db.commit()
    elif not user.google_id:
        user.google_id = google_id
        db.commit()
    
    access_token = create_access_token(user.id)
    
    redirect_url = f"{request.base_url}auth/login/success?token={access_token}"
    return RedirectResponse(redirect_url)

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)) -> Any:
    return current_user 