import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

logger = logging.getLogger(__name__)

# Moteur SQLAlchemy pour PostgreSQL avec driver psycopg
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def init_database() -> None:
    """Initialise la base de données :

    - Active automatiquement l'extension vectorielle pgvector
    - Crée les tables si elles n'existent pas encore
    """
    logger.info("Initialisation de PostgreSQL et vérification de l'extension pgvector...")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    logger.info("Extension pgvector initialisée avec succès.")

    # Création des tables SQLAlchemy
    Base.metadata.create_all(bind=engine)
    logger.info("Tables de la base de données vérifiées/créées.")


def get_db() -> Generator[Session, None, None]:
    """Générateur de session SQLAlchemy pour injection de dépendances FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
