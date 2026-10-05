import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, Document, DocumentPage
from dotenv import load_dotenv

load_dotenv()

# Fetch database credentials securely from environment variables
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "pii_db")

# Construct the database URL dynamically
DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# DB_URL = "postgresql+psycopg2://postgres:Redstone@localhost:5432/pii_db"

engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create PostgreSQL tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def save_processed_document_to_db(handler, file_path, pages_processed):
    """Persists document metadata and page records into PostgreSQL."""
    db = SessionLocal()
    try:
        doc = Document(
            filename=handler.filename,
            file_type=handler.get_file_type(),
            total_pages=handler.get_page_count(),
            storage_path=file_path,
            status="PROCESSED",
        )
        db.add(doc)
        db.flush()

        for idx, page_data in enumerate(pages_processed, start=1):
            page = DocumentPage(
                document_id=doc.id,
                page_number=idx,
                raw_text=page_data["raw_text"],
                redacted_text=page_data["redacted_text"],
                entity_mapping=page_data["mapping"],  # Stored as JSONB
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


def generate_document_summary(page_records):
    """Aggregates PII entity types and counts across all pages of a document."""
    summary = {}
    for page in page_records:
        mapping = page.entity_mapping or {}
        for placeholder, original_text in mapping.items():
            # Extract base entity type from placeholder (e.g., "[PERSON_1]" -> "PERSON")
            entity_type = placeholder.split("_")[0].replace("[", "")
            
            if entity_type not in summary:
                summary[entity_type] = {"count": 0, "instances": set()}
            
            summary[entity_type]["count"] += 1
            summary[entity_type]["instances"].add(original_text)
            
    # Convert sets to lists for JSON serialization
    for entity_type in summary:
        summary[entity_type]["instances"] = list(summary[entity_type]["instances"])
        
    return summary