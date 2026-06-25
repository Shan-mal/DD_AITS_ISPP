from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from core.database import get_db
from models.models import User, UserRole
from jose import jwt
from datetime import datetime, timedelta
import hashlib

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = "SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def hash_password(password: str) -> str:
    """Простое хеширование через SHA-256 (только для разработки)."""
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/register")
def register(email: str, password: str, full_name: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(password)
    db_user = User(email=email, password_hash=hashed, full_name=full_name)
    db.add(db_user)
    db.commit()
    return {"msg": "User created"}

@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or user.password_hash != hash_password(form_data.password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": str(user.id), "exp": expire}
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}