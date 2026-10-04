import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, Document, DocumentPage

# Configure DB connection string (Override with environment variable DATABASE_URL if set)
DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pii_db"
)
DB_URL = "postgresql+psycopg2://postgres:Redstone@localhost:5432/pii_db"

engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create PostgreSQL tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def save_document_to_db(handler, file_path, pages_text):
    """Save document metadata and page-level raw text into PostgreSQL."""
    db = SessionLocal()
    try:
        doc = Document(
            filename=handler.filename,
            file_type=handler.get_file_type(),
            total_pages=handler.get_page_count(),
            storage_path=file_path,
            status="UPLOADED",
        )
        db.add(doc)
        db.flush()  # Populates doc.id before committing

        for idx, text in enumerate(pages_text, start=1):
            page = DocumentPage(
                document_id=doc.id,
                page_number=idx,
                raw_text=text,
                entity_mapping={},
            )
            db.add(page)

        db.commit()
        db.refresh(doc)
        return doc
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()