import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    total_pages = Column(Integer, nullable=False, default=1)
    storage_path = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="UPLOADED")
    created_at = Column(DateTime, default=datetime.utcnow)

    pages = relationship(
        "DocumentPage", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_number = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=True)
    redacted_text = Column(Text, nullable=True)
    entity_mapping = Column(JSONB, nullable=True, default={})

    document = relationship("Document", back_populates="pages")