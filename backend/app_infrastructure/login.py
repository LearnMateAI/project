from app_infrastructure.authentication import verify_password

def authenticate_user(users_collection, email: str, password: str):
    """
    Returns the user dict on success, or None on failure.
    Deliberately does not reveal which field was wrong (SRS FR-2).
    """
    user = users_collection.find_one({"email": email.strip().lower()})
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {"id": str(user["_id"]), "name": user["name"], "email": user["email"]}