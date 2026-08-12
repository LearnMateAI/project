from fastapi import Header, HTTPException
import jwt
from app_infrastructure.authentication import decode_access_token

def get_current_user(authorization: str = Header(None)):
    """
    FastAPI dependency. Reads the 'Authorization: Bearer <token>' header,
    validates the JWT, and returns {id, email}.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    return {"id": payload["sub"], "email": payload["email"]}
