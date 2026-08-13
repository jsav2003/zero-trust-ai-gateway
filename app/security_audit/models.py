import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

# Vector preparation: 
# Uncomment the following import when adding pgvector.
# from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


class SecurityAuditLog(Base):
    """
    Database model representing a security audit log for prompts sent to the Gateway.
    Records the original prompt, sanitization results, and risk assessment.
    """
    __tablename__ = "security_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        # index=True is redundant; primary keys inherently have a unique index in PostgreSQL
        comment="Unique identifier for the audit log entry"
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Identifier of the user who submitted the prompt"
    )
    original_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The original, unedited prompt submitted by the user"
    )
    sanitized_prompt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="The sanitized version of the prompt, if PII or sensitive data was redacted"
    )
    risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Calculated risk score indicating potential security or compliance violations"
    )
    pii_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag indicating if Personally Identifiable Information was found in the prompt"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the prompt was received and audited"
    )
    
    # -------------------------------------------------------------------------
    # Vector Preparation (pgvector)
    # -------------------------------------------------------------------------
    # The structure allows seamless addition of a Vector column.
    # embedding: Mapped[Optional[Any]] = mapped_column(
    #     Vector(1536),  # e.g., OpenAI text-embedding-3-small dimension
    #     nullable=True,
    #     comment="Vector embeddings of the original/sanitized prompt for semantic search"
    # )

    # -------------------------------------------------------------------------
    # Advanced Indexing Strategy
    # -------------------------------------------------------------------------
    __table_args__ = (
        # Composite index for filtering by user and sorting by the most recent prompts
        Index("ix_security_audit_user_time_desc", "user_id", timestamp.desc()),
        # B-Tree index for sorting globally by timestamp (critical for audit dashboards)
        Index("ix_security_audit_timestamp_desc", timestamp.desc()),
    )
