from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import initialize_database, get_db
from app.routers.trainees import router as trainee_router
from app.routers.claims import router as claims_router, admin_router as admin_claims_router
from app.routers.analytics import router as analytics_router
from app.routers.employment import (
    router as employment_router,
    admin_router as admin_employment_router,
)
from app.routers.followups import (
    router as followup_router,
    admin_router as admin_followup_router,
)
from app.routers.auth import router as auth_router, seed_default_admin, seed_trainee_accounts
from app.routers.me import router as me_router
from app.routers.admin import router as admin_router
from app.routers.verification import router as verification_router


# Create / upgrade the SQLite schema before the application starts.
initialize_database()


app = FastAPI(
    title="KaushalTrace API",
    description="SIH26135 - Longitudinal Skill & Employment Outcome",
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Public/read APIs retained from the original application.
app.include_router(trainee_router)
app.include_router(claims_router)
app.include_router(analytics_router)
app.include_router(employment_router)
app.include_router(followup_router)

# Authentication and protected administrative controls.
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(admin_router)
app.include_router(admin_claims_router)
app.include_router(verification_router)
app.include_router(admin_employment_router)
app.include_router(admin_followup_router)


@app.on_event("startup")
def startup_seed():
    db = next(get_db())
    try:
        seed_default_admin(db)
        seed_trainee_accounts(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database": "connected",
    }


@app.get("/api/system/status")
def system_status(db: Session = Depends(get_db)):
    # Keep this deliberately lightweight; it is a UI health signal,
    # not a claim that an external ML service is running.
    from app.models import AdminUser, OutcomeClaim

    return {
        "status": "healthy",
        "database": "connected",
        "claims": db.query(OutcomeClaim).count(),
        "admins": db.query(AdminUser).count(),
        "verification_pipeline": "RULE_BASED",
    }


# Serve the SPA from FastAPI itself. API routes above are matched first.
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"

if frontend_dir.exists():
    app.mount(
        "/",
        StaticFiles(
            directory=str(frontend_dir),
            html=True,
        ),
        name="frontend",
    )
