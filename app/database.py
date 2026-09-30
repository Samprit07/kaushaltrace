from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./kaushaltrace.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database():
    """
    Create new tables and perform small, idempotent SQLite schema upgrades
    required by the enterprise admin workflow.

    This is intentionally lightweight for the hackathon's SQLite prototype.
    A production deployment should move these changes into Alembic migrations.
    """
    # Import models before create_all so SQLAlchemy sees every table.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    additions = {
        "outcome_claims": {
            "status": "VARCHAR DEFAULT 'PENDING'",
            "remarks": "TEXT",
            "status_updated_at": "VARCHAR",
        },
        "verification_records": {
            "confidence_score": "FLOAT",
            "override_remarks": "TEXT",
        },
        "followups": {
            "call_status": "VARCHAR DEFAULT 'PENDING'",
            "notes": "TEXT",
        },
    }

    inspector = inspect(engine)

    with engine.begin() as connection:
        for table_name, columns in additions.items():
            existing = {
                column["name"]
                for column in inspector.get_columns(table_name)
            }

            for column_name, sql_type in columns.items():
                if column_name not in existing:
                    connection.execute(
                        text(
                            f'ALTER TABLE "{table_name}" '
                            f'ADD COLUMN "{column_name}" {sql_type}'
                        )
                    )
