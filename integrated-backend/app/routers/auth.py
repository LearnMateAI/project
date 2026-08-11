"""
Accounts: register, log in, and confirm who the token belongs to.

The two error paths differ on purpose, and the difference is the whole security argument
of this file:

    register  says exactly what is wrong -- a form that cannot say "needs a number"
              cannot be completed
    login     says only that the combination was wrong -- "no account with that address"
              tells an attacker which addresses are worth attacking

The URLs and the {token, user} response shape are unchanged from the original backend, so
the existing React code keeps working.
"""

from fastapi import APIRouter, Depends, HTTPException

from ..auth import authenticate_user, create_access_token, register_new_user
from ..deps import get_current_user
from ..schemas import AuthResponse, LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest):
    """Create an account and log straight in."""
    try:
        user = register_new_user(payload.name, payload.email, payload.password)
    except ValueError as exc:
        # 409 for a taken address, 400 for anything the user can fix by retyping.
        status = 409 if "already exists" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc))

    return {"token": create_access_token(user["id"], user["email"]), "user": user}


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    """Exchange an email and password for a token."""
    user = authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {"token": create_access_token(user["id"], user["email"]), "user": user}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """
    Who this token belongs to.

    Read from the token rather than the database: the frontend calls it on every page
    load to decide whether a stored token is still good, and that question is answered
    entirely by whether the token verified.
    """
    return {"id": user["id"], "email": user["email"]}
