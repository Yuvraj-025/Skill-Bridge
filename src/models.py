from datetime import datetime, date, time
from typing import Optional, List
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Time, Enum
from sqlalchemy.orm import relationship
from pydantic import BaseModel, EmailStr, ConfigDict

from src.database import Base

# --- SQLAlchemy Enums ---
class RoleEnum(str, PyEnum):
    student = "student"
    trainer = "trainer"
    institution = "institution"
    programme_manager = "programme_manager"
    monitoring_officer = "monitoring_officer"

class AttendanceStatus(str, PyEnum):
    present = "present"
    absent = "absent"
    late = "late"

# --- SQLAlchemy Models ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    institution_id = Column(Integer, ForeignKey("users.id"), nullable=True) # self-referential or we can treat institution as a user
    created_at = Column(DateTime, default=datetime.utcnow)

class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    institution_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class BatchTrainer(Base):
    __tablename__ = "batch_trainers"
    batch_id = Column(Integer, ForeignKey("batches.id"), primary_key=True)
    trainer_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

class BatchStudent(Base):
    __tablename__ = "batch_students"
    batch_id = Column(Integer, ForeignKey("batches.id"), primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

class BatchInvite(Base):
    __tablename__ = "batch_invites"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    trainer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(AttendanceStatus), nullable=False)
    marked_at = Column(DateTime, default=datetime.utcnow)

# --- Pydantic Schemas ---
class UserSignup(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: RoleEnum
    institution_id: Optional[int] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class BatchCreate(BaseModel):
    name: str

class BatchInviteCreate(BaseModel):
    pass # No body required, created by trainer

class BatchJoin(BaseModel):
    token: str

class SessionCreate(BaseModel):
    batch_id: int
    title: str
    date: date
    start_time: time
    end_time: time

class AttendanceMark(BaseModel):
    session_id: int
    status: AttendanceStatus

class MonitoringTokenRequest(BaseModel):
    key: str

class AttendanceOut(BaseModel):
    id: int
    session_id: int
    student_id: int
    status: AttendanceStatus
    marked_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BatchSummary(BaseModel):
    batch_id: int
    batch_name: str
    total_students: int
    total_sessions: int
    attendance_rate: float
