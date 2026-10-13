import json
import logging
import os
from pathlib import Path
from typing import Generator, Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load environment variables
backend_env = Path(__file__).resolve().parent.parent / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
else:
    load_dotenv()

logger = logging.getLogger("veritas.database")

Base = declarative_base()

# Vector type handling: dynamically import pgvector if available
PGVECTOR_AVAILABLE = False
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    logger.warning("pgvector is not installed; vector column will use fallback type.")
    Vector = None

def get_database_url() -> str:
    """Retrieve normalized database URL from environment or return SQLite fallback."""
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if url:
        # Standardize postgres:// to postgresql:// for SQLAlchemy
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url
    
    # Default to persistent SQLite in data/ directory
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = data_dir / "veritas.db"
    return f"sqlite:///{sqlite_path}"

DB_URL = get_database_url()
IS_POSTGRES = DB_URL.startswith("postgresql://") or DB_URL.startswith("postgres://")

def create_app_engine():
    """Create database engine with automatic PostgreSQL connection attempt and SQLite fallback."""
    global DB_URL, IS_POSTGRES
    
    if IS_POSTGRES:
        try:
            eng = create_engine(
                DB_URL,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            # Test connectivity
            with eng.connect() as conn:
                if PGVECTOR_AVAILABLE:
                    try:
                        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                        conn.commit()
                    except Exception as ext_err:
                        logger.warning(f"Could not enable pgvector extension: {ext_err}")
                conn.execute(text("SELECT 1;"))
            logger.info(f"Connected to PostgreSQL database at {eng.url.host}:{eng.url.port or 5432}/{eng.url.database}")
            return eng, True
        except Exception as exc:
            logger.warning(
                f"PostgreSQL connection to {DB_URL} failed ({exc}). Falling back to local SQLite database."
            )
    
    # Fallback SQLite engine
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = data_dir / "veritas.db"
    sqlite_url = f"sqlite:///{sqlite_path}"
    
    eng = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
    )
    # Enable SQLite WAL mode
    try:
        with eng.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.commit()
    except Exception:
        pass
    
    DB_URL = sqlite_url
    IS_POSTGRES = False
    logger.info(f"Using SQLite database at {sqlite_path}")
    return eng, False

engine, IS_POSTGRES = create_app_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Initialize database tables using SQLAlchemy Base metadata."""
    try:
        # Import models so they are registered with Base
        import app.models.db_models  # noqa
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as exc:
        logger.error(f"Failed to initialize database tables: {exc}")

# Auto-initialize tables upon engine creation
init_db()
