import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

DATA_DIR = settings.data_dir
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = settings.get_database_url

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations(engine):
    """Adiciona colunas novas sem quebrar o banco existente (SQLite sem Alembic)."""
    migrations = [
        "ALTER TABLE customers ADD COLUMN msgs_ativo BOOLEAN DEFAULT 1",
        "ALTER TABLE configuracoes ADD COLUMN scheduler_hora_disparo INTEGER DEFAULT 9",
        "ALTER TABLE configuracoes ADD COLUMN director_alert_min_installments INTEGER DEFAULT 3",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Coluna já existe — ignorar
