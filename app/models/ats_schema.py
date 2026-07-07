from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictAtsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AtsScoreBreakdown(StrictAtsModel):
    contactInfo: int = Field(ge=0, le=10)
    professionalSummary: int = Field(ge=0, le=10)
    skills: int = Field(ge=0, le=15)
    workExperience: int = Field(ge=0, le=20)
    education: int = Field(ge=0, le=10)
    certifications: int = Field(ge=0, le=5)
    keywords: int = Field(ge=0, le=20)
    formatting: int = Field(ge=0, le=10)


class AtsScoreResponse(StrictAtsModel):
    resumeId: str
    source: Literal["parsed", "edited"]
    atsScore: int = Field(ge=0, le=100)
    scoreLevel: str
    summary: str
    scoreBreakdown: AtsScoreBreakdown
    strengths: list[str] = Field(default_factory=list)
    weakAreas: list[str] = Field(default_factory=list)
    missingSections: list[str] = Field(default_factory=list)
    keywordGaps: list[str] = Field(default_factory=list)
    formattingRisks: list[str] = Field(default_factory=list)
    improvementSuggestions: list[str] = Field(default_factory=list)


class AtsScoreSummary(StrictAtsModel):
    atsScore: int = Field(ge=0, le=100)
    scoreLevel: str


class CompareAtsScoreResponse(StrictAtsModel):
    resumeId: str
    originalResume: AtsScoreSummary
    editedResume: AtsScoreSummary
    improvement: int
    summary: str
    remainingSuggestions: list[str] = Field(default_factory=list)
