# SkillBridge Attendance Management API

## 1. Live API Base URL & Deployment Notes
**Base URL**: `https://skillbridge-api-h078.onrender.com/docs#/` 

**Deployment Notes**:
The application is designed to be easily deployable on Railway or Render. 
- Ensure you set the `DATABASE_URL` environment variable to your Neon PostgreSQL connection string.
- Set `JWT_SECRET` and `MONITORING_API_KEY` in your platform's environment variables.
- The start command is: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`

## 2. Local Setup Instructions

1. **Clone the repository and enter the directory**:
   ```bash
   cd submission
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Copy `.env.example` to `.env` and fill in the database URL. For local testing without a real Postgres instance, you can temporarily use SQLite by setting:
   ```
   DATABASE_URL=sqlite:///./skillbridge.db
   ```

5. **Run the server**:
   ```bash
   uvicorn src.main:app --reload
   ```

6. **Run Tests**:
   ```bash
   pytest tests/
   ```

7. **Seed Database** (Optional):
   ```bash
   python -m src.seed
   ```

## 3. Test Accounts
(Run `src.seed` script first to generate these accounts)

| Role | Email | Password |
|------|-------|----------|
| Programme Manager | pm@test.com | password123 |
| Monitoring Officer | monitor@test.com | password123 |
| Institution | inst1@test.com | password123 |
| Trainer | trainer1@test.com | password123 |
| Student | student1@test.com | password123 |

## 4. Sample Curl Commands

### Auth
**Signup**:
```bash
curl -X POST http://localhost:8000/auth/signup -H "Content-Type: application/json" -d '{"name": "John Doe", "email": "john@test.com", "password": "pw", "role": "student"}'
```

**Login**:
```bash
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email": "john@test.com", "password": "pw"}'
```
*(Extract the JWT token from the response for the following requests)*

### Batches (Requires Trainer/Institution Token)
**Create Batch**:
```bash
curl -X POST http://localhost:8000/batches -H "Authorization: Bearer <JWT_TOKEN>" -H "Content-Type: application/json" -d '{"name": "Morning Batch"}'
```

**Generate Invite (Requires Trainer Token)**:
```bash
curl -X POST http://localhost:8000/batches/1/invite -H "Authorization: Bearer <JWT_TOKEN>"
```

**Join Batch (Requires Student Token)**:
```bash
curl -X POST http://localhost:8000/batches/join -H "Authorization: Bearer <JWT_TOKEN>" -H "Content-Type: application/json" -d '{"token": "<INVITE_TOKEN>"}'
```

### Sessions & Attendance
**Create Session (Requires Trainer Token)**:
```bash
curl -X POST http://localhost:8000/sessions -H "Authorization: Bearer <JWT_TOKEN>" -H "Content-Type: application/json" -d '{"batch_id": 1, "title": "Day 1", "date": "2023-10-10", "start_time": "09:00:00", "end_time": "11:00:00"}'
```

**Mark Attendance (Requires Student Token)**:
```bash
curl -X POST http://localhost:8000/attendance/mark -H "Authorization: Bearer <JWT_TOKEN>" -H "Content-Type: application/json" -d '{"session_id": 1, "status": "present"}'
```

### Monitoring Officer Dual-Token Flow
**1. Get standard token via login**:
```bash
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email": "monitor@test.com", "password": "password123"}'
```

**2. Exchange for Monitoring Token**:
```bash
curl -X POST http://localhost:8000/auth/monitoring-token -H "Authorization: Bearer <STANDARD_JWT_TOKEN>" -H "Content-Type: application/json" -d '{"key": "test_monitoring_key_123"}'
```

**3. Access Monitoring Data**:
```bash
curl -X GET http://localhost:8000/monitoring/attendance -H "Authorization: Bearer <SCOPED_JWT_TOKEN>"
```

## 5. Schema Decisions
- **`batch_trainers` and `batch_students`**: Implemented as associative tables (many-to-many relationship) because a trainer can manage multiple batches, and a batch can have multiple trainers. Similarly for students.
- **`batch_invites`**: I decided to make invites a separate table linked to `batch_id` with an `expires_at` and `used` boolean flag. This ensures single-use invites that are securely tied to a specific generated token string.
- **Dual-Token Approach**: The Monitoring Officer relies on an elevated short-lived token. The initial token proves their identity (login), while the secondary token proves they have the out-of-band secret key to access sensitive global analytics. This separates authentication from specific elevated authorization scopes.

## 6. Project Status
- **Fully Working**: Authentication, RBAC via dependencies, Batch management, Invites, Session creation, and Attendance marking. Dual-token flow for Monitoring Officer. Global Exception Handling (422s, 404s).
- **Partially Done**: Tests. Five tests are implemented and test the core endpoints. More coverage could be added.
- **Skipped**: Alembic migrations. Given the prototype nature, I relied on SQLAlchemy `create_all()` directly.

## 7. What I'd do differently with more time
With more time, I would:
1. Implement Alembic for proper database migrations instead of `Base.metadata.create_all()`.
2. Add Redis for token revokation (blacklisting) upon logout, making the JWT system more secure.
3. Move away from sync SQLAlchemy towards `asyncpg` and asynchronous endpoints to leverage FastAPI's true concurrent performance.
