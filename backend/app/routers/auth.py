"""Login, registration and current user."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from .. import database as db
from ..auth import hash_password, verify_password, create_token, get_current_user
from ..logger import log
from ..schemas import RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, summary="Create a new user account")
def register(body: RegisterRequest):
    if db.get_user_by_name(body.username):
        raise HTTPException(status_code=409, detail="This username is already taken.")
    db.create_user(body.username, hash_password(body.password), role="user")
    log.info(f"New user registered: {body.username}")
    return TokenResponse(access_token=create_token(body.username, "user"), username=body.username, role="user")


@router.post("/login", response_model=TokenResponse,
             summary="Log in (form fields: username, password) and get a token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = db.get_user_by_name(form.username)
    if user is None or not verify_password(form.password, user["password_hash"]):
        log.warning(f"Failed login for '{form.username}'")
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    log.info(f"Login: {user['username']} ({user['role']})")
    return TokenResponse(access_token=create_token(user["username"], user["role"]),
                         username=user["username"], role=user["role"])


@router.get("/me", response_model=UserOut, summary="Get the logged-in user")
def me(user: dict = Depends(get_current_user)):
    return user
