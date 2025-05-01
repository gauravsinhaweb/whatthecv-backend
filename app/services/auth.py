from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional

from app.core.config import settings
from app.core.security import verify_password, get_password_hash, generate_otp
from app.db.base import get_db
from app.models.user import User
from app.models.otp import OTP
from app.schemas.user import TokenPayload, UserCreate
from app.utils.email import send_otp_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def create_user(db: Session, user_data: UserCreate) -> User:
    db_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password) if user_data.password else None,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

async def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        
        if datetime.fromtimestamp(token_data.exp) < datetime.utcnow():
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == token_data.sub).first()
    
    if not user:
        raise credentials_exception
    
    return user

async def create_otp(db: Session, email: str, purpose: str) -> str:
    otp_code = generate_otp()
    
    existing_otp = db.query(OTP).filter(
        OTP.email == email,
        OTP.purpose == purpose
    ).first()
    
    if existing_otp:
        existing_otp.code = otp_code
        existing_otp.expires_at = datetime.now() + timedelta(minutes=10)
        existing_otp.attempts = 0
        db.commit()
    else:
        new_otp = OTP(
            email=email,
            code=otp_code,
            purpose=purpose
        )
        db.add(new_otp)
        db.commit()
    
    await send_otp_email(email, otp_code, purpose)
    
    return otp_code

async def verify_otp(db: Session, email: str, code: str, purpose: str) -> bool:
    otp = db.query(OTP).filter(
        OTP.email == email,
        OTP.purpose == purpose
    ).first()
    
    if not otp:
        return False
    
    if otp.expires_at < datetime.now():
        return False
    
    otp.attempts += 1
    db.commit()
    
    if otp.attempts >= 5:
        db.delete(otp)
        db.commit()
        return False
    
    if otp.code != code:
        return False
    
    db.delete(otp)
    db.commit()
    
    return True 