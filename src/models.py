"""Typed data models for clinical session note extraction."""

from pydantic import BaseModel, Field
from typing import Optional


class SessionMetadata(BaseModel):
    """Header-level metadata for the session."""
    patient_name: str = Field(
        ...,
        description="Patient name in LASTNAME, Firstname format"
    )
    dob: Optional[str] = Field(
        None,
        description="Date of birth (e.g., 2/4/1995)"
    )
    session_date: str = Field(
        ...,
        description="Full session date (e.g., January 28, 2026)"
    )
    session_time: str = Field(
        ...,
        description="Session time (e.g., 10:00am)"
    )
    session_type: str = Field(
        ...,
        description="Type of session as stated in the notes (e.g., Structured Background History Interview, Therapy Session (Virtual))"
    )


class SummaryItem(BaseModel):
    """A sub-section within the summary, with a bold heading and body text."""
    heading: str = Field(
        ...,
        description="Bold sub-header name for this summary sub-section"
    )
    content: str = Field(
        default="",
        description="The paragraph text for this summary sub-section"
    )


class DetailItem(BaseModel):
    """A single detail bullet point with a bold heading and body text."""
    heading: str = Field(
        ...,
        description="Bold sub-header name for this detail"
    )
    content: str = Field(
        default="",
        description="The paragraph text for this detail"
    )


class SessionReport(BaseModel):
    """Complete structured output from the LLM for a clinical session."""
    metadata: SessionMetadata
    summary_intro: str = Field(
        ...,
        description="The opening summary paragraph (before any sub-sections)"
    )
    summary_sections: list[SummaryItem] = Field(
        default_factory=list,
        description="List of summary sub-sections, each with a heading and content"
    )
    details: list[DetailItem] = Field(
        default_factory=list,
        description="List of detail sections with heading and content"
    )
    next_steps: list[str] = Field(
        default_factory=list,
        description="List of suggested next steps"
    )

