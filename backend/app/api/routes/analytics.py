from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import decode_access_token
from app.models import User
from app.services import analytics_service

router = APIRouter(prefix="/api", tags=["analytics"])

_optional_bearer = HTTPBearer(auto_error=False)


class LogEventRequest(BaseModel):
    event_name: str
    metadata: dict | None = None


@router.post("/events")
def log_event(
    req: LogEventRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
):
    """
    Auth is optional here on purpose: some events (page_view) can fire before a
    person has signed in. If a valid token is present we attach the user_id; if not,
    the event is still recorded, just without one.
    """
    user_id = None
    if credentials:
        email = decode_access_token(credentials.credentials)
        if email:
            user = db.query(User).filter(User.email == email).first()
            if user:
                user_id = user.id

    try:
        analytics_service.log_event(db, req.event_name, user_id=user_id, metadata=req.metadata)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"logged": True}


@router.get("/analytics/summary")
def analytics_summary(days: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Requires auth (any signed-in user, not just an admin -- this app has no admin/role
    concept yet). Fine for a portfolio project's own visibility into usage; add a real
    role check before treating this as a private admin dashboard.
    """
    return analytics_service.get_summary(db, days=days)
