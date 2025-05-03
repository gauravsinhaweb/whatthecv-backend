from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional, Dict, Any, Tuple
from app.utils.errors import AuthError

from app.core.config import settings
from app.core.security import verify_password, get_password_hash, generate_otp
from app.db.base import get_db
from app.models.user import User
from app.models.otp import OTP
from app.schemas.user import TokenPayload, UserCreate
from app.utils.email import send_otp_email
from app.utils.supabase import (
    create_supabase_user, 
    authenticate_supabase_user,
    get_supabase_user
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

async def create_user(db: Session, user_data: UserCreate) -> Tuple[User, Dict[str, Any]]:
    supabase_user = None
    supabase_error = None
    
    if user_data.password:
        try:
            supabase_response = await create_supabase_user(user_data.email, user_data.password)
            supabase_user = supabase_response.user
        except AuthError as e:
            supabase_error = {"error": str(e)}
    
    db_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password) if user_data.password else None,
        supabase_id=supabase_user.id if supabase_user else None
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user, {"supabase_user": supabase_user, "error": supabase_error}

async def authenticate_user(db: Session, email: str, password: str) -> Tuple[Optional[User], Dict[str, Any]]:
    user = db.query(User).filter(User.email == email).first()
    supabase_user = None
    supabase_error = None
    
    if not user or not user.hashed_password:
        return None, {"error": "Invalid credentials"}
    
    if not verify_password(password, user.hashed_password):
        return None, {"error": "Invalid credentials"}
    
    # Also authenticate with Supabase if there's a supabase_id
    if user.supabase_id:
        try:
            supabase_response = await authenticate_supabase_user(email, password)
            supabase_user = supabase_response.user
        except AuthError as e:
            supabase_error = {"error": str(e)}
    
    return user, {"supabase_user": supabase_user, "error": supabase_error}

async def validate_token(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        
        if datetime.fromtimestamp(token_data.exp) < datetime.now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == token_data.sub).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Validate with Supabase if there's a supabase_id
    if user.supabase_id:
        try:
            supabase_user = await get_supabase_user(token)
            if not supabase_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Supabase authentication",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception:
            # If Supabase validation fails, we can still use our local validation
            pass
    
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return await validate_token(token, db)

async def get_optional_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Optional[User]:
    if not token:
        return None
    
    try:
        return await validate_token(token, db)
    except HTTPException:
        return None

async def create_otp(db: Session, email: str, purpose: str) -> OTP:
    otp_code = generate_otp()
    
    existing_otp = db.query(OTP).filter(OTP.email == email, OTP.purpose == purpose).first()
    if existing_otp:
        existing_otp.code = otp_code
        existing_otp.expires_at = datetime.now() + timedelta(minutes=10)
        existing_otp.attempts = 0
        db.commit()
        db.refresh(existing_otp)
        otp_obj = existing_otp
    else:
        otp_obj = OTP(email=email, code=otp_code, purpose=purpose)
        db.add(otp_obj)
        db.commit()
        db.refresh(otp_obj)
    
    # Send OTP email
    await send_otp_email(email, otp_code, purpose)
    
    return otp_obj

async def verify_otp(db: Session, email: str, code: str, purpose: str) -> bool:
    otp = db.query(OTP).filter(OTP.email == email, OTP.purpose == purpose).first()
    
    if not otp:
        return False
    
    if otp.expires_at < datetime.now():
        return False
    
    if otp.attempts >= 3:
        return False
    
    if otp.code != code:
        otp.attempts += 1
        db.commit()
        return False
    
    # Successfully verified, clean up OTP
    db.delete(otp)
    db.commit()
    
    return True 