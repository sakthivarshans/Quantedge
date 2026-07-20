import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.models import User
from app.services.analytics_service import log_event

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str  # the credential returned by Google Identity Services on the frontend


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    name: str | None = None
    picture_url: str | None = None


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    if len(req.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")
    user = User(email=req.email, hashed_password=hash_password(req.password), auth_provider="password")
    db.add(user)
    db.commit()
    db.refresh(user)
    log_event(db, "signup", user_id=user.id, metadata={"auth_provider": "password"})
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token, email=user.email, name=user.name, picture_url=user.picture_url)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    # Guard against Google-only accounts (hashed_password is None for them) rather than
    # letting verify_password raise on a None hash -- a wrong-provider account should
    # look like "incorrect credentials" to the caller, not crash the request.
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    log_event(db, "login", user_id=user.id)
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token, email=user.email, name=user.name, picture_url=user.picture_url)


@router.post("/google", response_model=TokenResponse)
@limiter.limit("10/minute")
def google_login(request: Request, req: GoogleLoginRequest, db: Session = Depends(get_db)):
    """
    Verifies the ID token Google Identity Services returned to the frontend, then
    finds-or-creates a local user for that Google account and issues our own JWT --
    the rest of the app only ever deals with our own tokens, never Google's directly.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google Sign-In is not configured on this server (GOOGLE_CLIENT_ID unset)",
        )

    try:
        payload = google_id_token.verify_oauth2_token(
            req.id_token, google_requests.Request(), GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential")

    if not payload.get("email_verified", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email is not verified")

    google_sub = payload["sub"]
    email = payload["email"]
    name = payload.get("name")
    picture = payload.get("picture")

    user = db.query(User).filter(User.google_sub == google_sub).first()
    is_new_user = False
    if user is None:
        # Also check by email, in case this person already registered with a password --
        # link the Google identity to that existing account rather than creating a duplicate.
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, auth_provider="google", google_sub=google_sub, name=name, picture_url=picture)
            db.add(user)
            is_new_user = True
        else:
            user.google_sub = google_sub
            user.name = user.name or name
            user.picture_url = user.picture_url or picture
        db.commit()
        db.refresh(user)

    if is_new_user:
        log_event(db, "signup", user_id=user.id, metadata={"auth_provider": "google"})
    log_event(db, "login_google", user_id=user.id)

    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token, email=user.email, name=user.name, picture_url=user.picture_url)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id, "email": current_user.email, "name": current_user.name,
        "picture_url": current_user.picture_url, "auth_provider": current_user.auth_provider,
    }
