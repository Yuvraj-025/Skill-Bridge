from datetime import datetime, timedelta, date, time
from typing import List
import uuid

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from src.database import engine, Base, get_db
from src.models import (
    User, Batch, BatchTrainer, BatchStudent, BatchInvite, Session as DBSession, Attendance,
    RoleEnum, AttendanceStatus,
    UserSignup, UserLogin, TokenResponse, BatchCreate, BatchJoin, SessionCreate,
    AttendanceMark, AttendanceOut, BatchSummary, MonitoringTokenRequest
)
from src.auth import (
    get_password_hash, verify_password, create_access_token,
    RequireRole, get_current_user_token, MONITORING_API_KEY
)

# Create tables if they don't exist (useful for testing, in prod use alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SkillBridge API")

# --- Exception Handlers ---
@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    # Foreign key violations or unique constraint violations
    if "foreign key constraint" in str(exc.orig).lower() or "fk_" in str(exc.orig).lower():
         return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Referenced resource not found (e.g., batch_id or session_id)"},
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Database integrity error (e.g., duplicate email)"},
    )

# --- Auth Endpoints ---
@app.post("/auth/signup", response_model=TokenResponse)
def signup(user: UserSignup, db: Session = Depends(get_db)):
    # Check if email exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=422, detail="Email already registered")
    
    new_user = User(
        name=user.name,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        role=user.role,
        institution_id=user.institution_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    token = create_access_token({"user_id": new_user.id, "role": new_user.role.value})
    return {"access_token": token}

@app.post("/auth/login", response_model=TokenResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"user_id": db_user.id, "role": db_user.role.value})
    return {"access_token": token}

@app.post("/auth/monitoring-token", response_model=TokenResponse)
def get_monitoring_token(
    req: MonitoringTokenRequest, 
    token_payload: dict = Depends(RequireRole([RoleEnum.monitoring_officer]))
):
    if req.key != MONITORING_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Issue a 1-hour token scoped specifically for monitoring
    scoped_token = create_access_token(
        data={"user_id": token_payload["user_id"], "role": RoleEnum.monitoring_officer.value, "scope": "monitoring"},
        expires_delta=timedelta(hours=1)
    )
    return {"access_token": scoped_token}

# --- Batch Endpoints ---
@app.post("/batches", status_code=status.HTTP_201_CREATED)
def create_batch(
    batch: BatchCreate, 
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.trainer, RoleEnum.institution]))
):
    user_id = token_payload["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    
    institution_id = user.institution_id if user.role == RoleEnum.trainer else user.id
    if not institution_id:
        raise HTTPException(status_code=400, detail="User not associated with an institution")

    new_batch = Batch(name=batch.name, institution_id=institution_id)
    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)
    
    if user.role == RoleEnum.trainer:
        # Automatically assign the creator trainer to this batch
        batch_trainer = BatchTrainer(batch_id=new_batch.id, trainer_id=user.id)
        db.add(batch_trainer)
        db.commit()
        
    return {"id": new_batch.id, "name": new_batch.name}

@app.post("/batches/{id}/invite")
def generate_batch_invite(
    id: int, 
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.trainer]))
):
    # Verify trainer is assigned to this batch
    trainer_id = token_payload["user_id"]
    is_assigned = db.query(BatchTrainer).filter_by(batch_id=id, trainer_id=trainer_id).first()
    if not is_assigned:
        raise HTTPException(status_code=403, detail="Not assigned to this batch")
        
    invite = BatchInvite(
        batch_id=id,
        token=str(uuid.uuid4()),
        created_by=trainer_id,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return {"invite_token": invite.token, "expires_at": invite.expires_at}

@app.post("/batches/join")
def join_batch(
    join_req: BatchJoin,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.student]))
):
    student_id = token_payload["user_id"]
    invite = db.query(BatchInvite).filter(BatchInvite.token == join_req.token).first()
    
    if not invite or invite.used or invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Invalid or expired invite token")
        
    # Check if already joined
    existing = db.query(BatchStudent).filter_by(batch_id=invite.batch_id, student_id=student_id).first()
    if not existing:
        db.add(BatchStudent(batch_id=invite.batch_id, student_id=student_id))
        invite.used = True
        db.commit()
        
    return {"detail": "Successfully joined batch", "batch_id": invite.batch_id}

# --- Session Endpoints ---
@app.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    session: SessionCreate,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.trainer]))
):
    trainer_id = token_payload["user_id"]
    is_assigned = db.query(BatchTrainer).filter_by(batch_id=session.batch_id, trainer_id=trainer_id).first()
    if not is_assigned:
        raise HTTPException(status_code=403, detail="Not assigned to this batch")
        
    new_session = DBSession(
        batch_id=session.batch_id,
        trainer_id=trainer_id,
        title=session.title,
        date=session.date,
        start_time=session.start_time,
        end_time=session.end_time
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

# --- Attendance Endpoints ---
@app.post("/attendance/mark")
def mark_attendance(
    attendance: AttendanceMark,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.student]))
):
    student_id = token_payload["user_id"]
    
    # Verify session exists and student is enrolled in the batch
    session = db.query(DBSession).filter(DBSession.id == attendance.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    is_enrolled = db.query(BatchStudent).filter_by(batch_id=session.batch_id, student_id=student_id).first()
    if not is_enrolled:
        raise HTTPException(status_code=403, detail="Not enrolled in this batch")
        
    # Check if attendance already marked
    existing = db.query(Attendance).filter_by(session_id=attendance.session_id, student_id=student_id).first()
    if existing:
        existing.status = attendance.status
        existing.marked_at = datetime.utcnow()
    else:
        new_att = Attendance(session_id=attendance.session_id, student_id=student_id, status=attendance.status)
        db.add(new_att)
        
    db.commit()
    return {"detail": "Attendance marked successfully"}

@app.get("/sessions/{id}/attendance", response_model=List[AttendanceOut])
def get_session_attendance(
    id: int,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.trainer]))
):
    return db.query(Attendance).filter(Attendance.session_id == id).all()

# --- Summary Endpoints ---
@app.get("/batches/{id}/summary")
def get_batch_summary(
    id: int,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.institution]))
):
    # Enforce that institution owns the batch
    institution_id = token_payload["user_id"]
    batch = db.query(Batch).filter(Batch.id == id, Batch.institution_id == institution_id).first()
    if not batch:
        raise HTTPException(status_code=403, detail="Batch not found or not owned by institution")
        
    total_students = db.query(func.count(BatchStudent.student_id)).filter_by(batch_id=id).scalar()
    total_sessions = db.query(func.count(DBSession.id)).filter_by(batch_id=id).scalar()
    
    return {
        "batch_id": id,
        "batch_name": batch.name,
        "total_students": total_students,
        "total_sessions": total_sessions
    }

@app.get("/institutions/{id}/summary")
def get_institution_summary(
    id: int,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.programme_manager]))
):
    total_batches = db.query(func.count(Batch.id)).filter_by(institution_id=id).scalar()
    return {"institution_id": id, "total_batches": total_batches}

@app.get("/programme/summary")
def get_programme_summary(
    db: Session = Depends(get_db),
    token_payload: dict = Depends(RequireRole([RoleEnum.programme_manager]))
):
    total_institutions = db.query(func.count(User.id)).filter(User.role == RoleEnum.institution).scalar()
    total_students = db.query(func.count(User.id)).filter(User.role == RoleEnum.student).scalar()
    return {"total_institutions": total_institutions, "total_students": total_students}

# --- Monitoring Officer Endpoint ---
@app.get("/monitoring/attendance")
def get_monitoring_attendance(
    db: Session = Depends(get_db),
    token_payload: dict = Depends(get_current_user_token)
):
    # Strictly validate the scoped token
    if token_payload.get("role") != RoleEnum.monitoring_officer.value or token_payload.get("scope") != "monitoring":
        raise HTTPException(status_code=403, detail="Invalid or missing scoped monitoring token")
        
    recent_attendance = db.query(Attendance).order_by(Attendance.marked_at.desc()).limit(100).all()
    return recent_attendance

# Requirement: /monitoring/attendance must return 405 for any non-GET request
@app.api_route("/monitoring/attendance", methods=["POST", "PUT", "DELETE", "PATCH"])
def monitoring_attendance_not_allowed():
    raise HTTPException(status_code=405, detail="Method Not Allowed")
