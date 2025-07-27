from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import app.db
from app.db import fix_mongo_id

router = APIRouter()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    user_id: str
    email: str
    name: Optional[str] = None
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str
    name: Optional[str] = None

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await app.db.db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/register")
async def register_user(user: UserCreate):
    existing = await app.db.db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_doc = {
        "email": user.email,
        "hashed_password": get_password_hash(user.password),
        "name": user.name or "",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await app.db.db.users.insert_one(user_doc)
    return {"message": "User registered successfully", "user_id": str(result.inserted_id)}

@router.post("/login", response_model=Token)
async def login_user(user: UserLogin):
    db_user = await app.db.db.users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access_token = create_access_token(
        data={"sub": str(db_user["_id"]), "email": db_user["email"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    db_user = fix_mongo_id(db_user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user["_id"],
        "email": db_user["email"],
        "name": db_user.get("name", "")
    }

@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    current_user = fix_mongo_id(current_user)
    return {
        "user_id": current_user["_id"],
        "email": current_user["email"],
        "name": current_user.get("name", ""),
        "created_at": current_user["created_at"]
    } 