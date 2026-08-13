import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

# Fortune 500 Paranoid Type Aliases
# Enforce max length to prevent Denial of Service via memory exhaustion from massive payloads
# Strip whitespace ensures clean data ingestion
PromptText = Annotated[
    str, 
    StringConstraints(strip_whitespace=True, max_length=100_000)
]

class SecurityAuditLogBase(BaseModel):
    """Base schema for Security Audit Log containing common fields."""
    
    # Enable strict parsing mode to reject implicit type casting (e.g., passing string "1" to a float field)
    model_config = ConfigDict(strict=True)

    user_id: str = Field(
        ..., 
        max_length=255, 
        description="Identifier of the user who submitted the prompt."
    )
    original_prompt: PromptText = Field(
        ..., 
        description="The original, unmodified prompt submitted by the user. Max 100k chars to prevent DoS."
    )
    sanitized_prompt: Optional[PromptText] = Field(
        default=None, 
        description="The prompt after sanitization, if any sensitive data was removed."
    )
    risk_score: float = Field(
        default=0.0, 
        ge=0.0, 
        le=10.0, 
        description="The calculated risk score of the prompt, strictly ranging from 0.0 to 10.0."
    )
    pii_detected: bool = Field(
        default=False, 
        description="Flag indicating whether Personally Identifiable Information was detected."
    )


class SecurityAuditLogCreate(SecurityAuditLogBase):
    """Schema for creating a new Security Audit Log entry."""
    pass


class SecurityAuditLogRead(SecurityAuditLogBase):
    """Schema for reading a Security Audit Log entry from the database."""
    id: uuid.UUID = Field(
        ..., 
        description="The unique identifier of the audit log entry."
    )
    timestamp: datetime = Field(
        ..., 
        description="The exact time the prompt was processed and audited."
    )

    # Allow reading from SQLAlchemy models while maintaining strict mode
    model_config = ConfigDict(from_attributes=True, strict=True)
