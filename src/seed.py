from datetime import datetime, date, time
from sqlalchemy.orm import Session
from src.database import engine, Base, SessionLocal
from src.models import (
    User, Batch, BatchTrainer, BatchStudent, Session as DBSession, Attendance,
    RoleEnum, AttendanceStatus
)
from src.auth import get_password_hash

def seed_data(db: Session):
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    # Check if already seeded
    if db.query(User).count() > 0:
        print("Database already contains data. Skipping seed.")
        return

    print("Seeding Users...")
    pw_hash = get_password_hash("password123")
    
    # Programme Manager
    pm = User(name="Program Manager", email="pm@test.com", hashed_password=pw_hash, role=RoleEnum.programme_manager)
    # Monitoring Officer
    mo = User(name="Monitor", email="monitor@test.com", hashed_password=pw_hash, role=RoleEnum.monitoring_officer)
    db.add_all([pm, mo])
    db.commit()

    # 2 Institutions
    inst1 = User(name="Inst 1", email="inst1@test.com", hashed_password=pw_hash, role=RoleEnum.institution)
    inst2 = User(name="Inst 2", email="inst2@test.com", hashed_password=pw_hash, role=RoleEnum.institution)
    db.add_all([inst1, inst2])
    db.commit()

    # 4 Trainers
    trainers = []
    for i in range(1, 5):
        t = User(name=f"Trainer {i}", email=f"trainer{i}@test.com", hashed_password=pw_hash, role=RoleEnum.trainer, institution_id=inst1.id if i <= 2 else inst2.id)
        db.add(t)
        trainers.append(t)
    db.commit()

    # 15 Students
    students = []
    for i in range(1, 16):
        s = User(name=f"Student {i}", email=f"student{i}@test.com", hashed_password=pw_hash, role=RoleEnum.student)
        db.add(s)
        students.append(s)
    db.commit()

    print("Seeding Batches...")
    # 3 Batches
    b1 = Batch(name="Batch A", institution_id=inst1.id)
    b2 = Batch(name="Batch B", institution_id=inst1.id)
    b3 = Batch(name="Batch C", institution_id=inst2.id)
    db.add_all([b1, b2, b3])
    db.commit()

    # Assign trainers to batches
    db.add(BatchTrainer(batch_id=b1.id, trainer_id=trainers[0].id))
    db.add(BatchTrainer(batch_id=b2.id, trainer_id=trainers[1].id))
    db.add(BatchTrainer(batch_id=b3.id, trainer_id=trainers[2].id))
    
    # Assign 5 students to each batch
    for i in range(5):
        db.add(BatchStudent(batch_id=b1.id, student_id=students[i].id))
        db.add(BatchStudent(batch_id=b2.id, student_id=students[i+5].id))
        db.add(BatchStudent(batch_id=b3.id, student_id=students[i+10].id))
    db.commit()

    print("Seeding Sessions and Attendance...")
    # 8 Sessions
    sessions = []
    for i in range(1, 9):
        batch_id = b1.id if i <= 3 else (b2.id if i <= 5 else b3.id)
        trainer_id = trainers[0].id if batch_id == b1.id else (trainers[1].id if batch_id == b2.id else trainers[2].id)
        sess = DBSession(
            batch_id=batch_id,
            trainer_id=trainer_id,
            title=f"Session {i}",
            date=date.today(),
            start_time=time(10, 0),
            end_time=time(12, 0)
        )
        db.add(sess)
        sessions.append(sess)
    db.commit()

    # Attendance
    for sess in sessions:
        # Get students for this session's batch
        batch_students = db.query(BatchStudent).filter_by(batch_id=sess.batch_id).all()
        for bs in batch_students:
            att = Attendance(
                session_id=sess.id,
                student_id=bs.student_id,
                status=AttendanceStatus.present
            )
            db.add(att)
    db.commit()
    print("Seeding complete!")

if __name__ == "__main__":
    db = SessionLocal()
    seed_data(db)
    db.close()
