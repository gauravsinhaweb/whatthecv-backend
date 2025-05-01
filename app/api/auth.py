from fastapi import APIRouter, Depends, HTTPException, status, Request
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
    
    user = await create_user(db, user_data)
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
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified",
        )
    
    access_token = create_access_token(user.id)
    return {"access_token": access_token, "token_type": "bearer"}

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

@router.get("/google/login")
async def google_login() -> Any:
    auth_url = await get_google_auth_url()
    return {"auth_url": auth_url}

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
        user = await create_user(db, user_data)
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
async def get_me(current_user: User = Depends(get_current_user)) -> Any:
    return current_user 