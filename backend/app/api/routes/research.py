from app.core.time import utcnow
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, ResearchSession
from app.services.research_service import run_cell

router = APIRouter(prefix="/api/research", tags=["research"])


class RunCellRequest(BaseModel):
    cell_type: str
    params: dict


@router.post("/run-cell")
def run_cell_endpoint(req: RunCellRequest, user: User = Depends(get_current_user)):
    try:
        result = run_cell(req.cell_type, req.params)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"result": result}


class SaveSessionRequest(BaseModel):
    name: str
    cells: list[dict]


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sessions = (
        db.query(ResearchSession)
        .filter(ResearchSession.user_id == user.id)
        .order_by(ResearchSession.updated_at.desc())
        .all()
    )
    return [
        {"id": s.id, "name": s.name, "num_cells": len(s.cells or []), "updated_at": s.updated_at.isoformat()}
        for s in sessions
    ]


@router.post("/sessions")
def save_session(req: SaveSessionRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = ResearchSession(user_id=user.id, name=req.name, cells=req.cells)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "name": session.name}


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.query(ResearchSession).filter(
        ResearchSession.id == session_id, ResearchSession.user_id == user.id
    ).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"id": session.id, "name": session.name, "cells": session.cells}


@router.put("/sessions/{session_id}")
def update_session(session_id: int, req: SaveSessionRequest, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    session = db.query(ResearchSession).filter(
        ResearchSession.id == session_id, ResearchSession.user_id == user.id
    ).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session.name = req.name
    session.cells = req.cells
    session.updated_at = utcnow()
    db.commit()
    return {"id": session.id, "name": session.name}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.query(ResearchSession).filter(
        ResearchSession.id == session_id, ResearchSession.user_id == user.id
    ).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"deleted": True}
