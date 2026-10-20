"""Strict contracts for untrusted model output. IDs are assigned by application code."""
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1800)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
ID = Annotated[str, StringConstraints(pattern=r"^[ECP][0-9]{4,6}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Citation(StrictModel):
    evidence_id: ID
    quote: Text


class Concept(StrictModel):
    topic: Name
    explanation: Text
    prerequisites: list[Name] = Field(max_length=8)
    caveats: list[Text] = Field(max_length=8)
    citations: list[Citation] = Field(min_length=1, max_length=5)


class Extraction(StrictModel):
    concepts: list[Concept] = Field(max_length=10)


class EvidenceReference(StrictModel):
    evidence_id: ID


class SelectedConcept(StrictModel):
    topic: Name
    explanation: Text
    prerequisites: list[Name] = Field(max_length=8)
    caveats: list[Text] = Field(max_length=8)
    citations: list[EvidenceReference] = Field(min_length=1, max_length=5)


class OutlineSection(StrictModel):
    heading: Name
    concept_ids: list[ID] = Field(min_length=1, max_length=8)


class Outline(StrictModel):
    title: Name
    sections: list[OutlineSection] = Field(min_length=1, max_length=30)


class Paragraph(StrictModel):
    text: Text
    concept_ids: list[ID] = Field(min_length=1, max_length=8)


class WrittenSection(StrictModel):
    paragraphs: list[Paragraph] = Field(min_length=1, max_length=8)


class Assessment(StrictModel):
    item_id: ID
    verdict: Literal["supported", "unsupported", "uncertain"]
    reason: Text


class Review(StrictModel):
    assessments: list[Assessment] = Field(min_length=1, max_length=12)


class FactualRisk(StrictModel):
    item_id: ID
    risk: Literal["no_obvious_issue", "needs_review"]
    reason: Text


class FactualReview(StrictModel):
    assessments: list[FactualRisk] = Field(min_length=1, max_length=12)


class EditorialAssessment(StrictModel):
    item_id: ID
    decision: Literal["technical", "exclude", "uncertain"]
    reason: Text
