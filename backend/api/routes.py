from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from database.db import users_collection
from app_infrastructure.authentication import create_access_token
from app_infrastructure.register import register_new_user
from app_infrastructure.login import authenticate_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    user: dict

@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest):
    try:
        user = register_new_user(users_collection, payload.name, payload.email, payload.password)
    except ValueError as e:
        if "already exists" in str(e):
            status_code=409
        else:
            status_code=400
        raise HTTPException(status_code=status_code, detail=str(e))
    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": user}

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    user = authenticate_user(users_collection, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": user}