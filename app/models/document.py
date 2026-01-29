"""
Document ORM model for storing reference academic documents.
These are the documents that user submissions will be compared against.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime

from app.database import Base


class Document(Base):
    """
    Represents an academic document in the reference repository.

    Attributes:
        id: Unique identifier
        title: Document title (e.g., "Mitochondria - Wikipedia")
        content: The full text content of the document
        category: Subject category (e.g., "Biology", "Computer Science")
        source: Origin of the document (e.g., "Wikipedia", "Thesis Abstract")
        created_at: Timestamp when the document was added
    """

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    source = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title='{self.title}', category='{self.category}')>"
