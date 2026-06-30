from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_optional_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExperienceSectionItem(StrictBaseModel):
    position: str = ""
    company: str = ""
    location: str = ""
    jobType: str = ""
    reasonForLeaving: str = ""
    start: str = ""
    end: str = ""
    achievements: list[str] = Field(default_factory=list)

    @field_validator("position", "company", "location", "jobType", "reasonForLeaving", "start", "end", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class EducationSectionItem(StrictBaseModel):
    degree: str = ""
    school: str = ""
    faculty: str = ""
    department: str = ""
    location: str = ""
    years: str = ""
    start: str = ""
    end: str = ""
    highlights: list[str] = Field(default_factory=list)

    @field_validator("degree", "school", "faculty", "department", "location", "years", "start", "end", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class SkillSectionItem(StrictBaseModel):
    name: str = ""
    level: str = ""

    @field_validator("name", "level", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class CourseSectionItem(StrictBaseModel):
    course: str = ""
    institution: str = ""
    start: str = ""
    end: str = ""

    @field_validator("course", "institution", "start", "end", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class LanguageSectionItem(StrictBaseModel):
    language: str = ""
    level: str = ""

    @field_validator("language", "level", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class ReferenceSectionItem(StrictBaseModel):
    name: str = ""
    company: str = ""
    email: str = ""
    phone: str = ""

    @field_validator("name", "company", "email", "phone", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class LinkSectionItem(StrictBaseModel):
    label: str = ""
    link: str = ""

    @field_validator("label", "link", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class InternshipSectionItem(StrictBaseModel):
    position: str = ""
    company: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    achievements: list[str] = Field(default_factory=list)

    @field_validator("position", "company", "location", "start", "end", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


SectionItem = (
    ExperienceSectionItem
    | EducationSectionItem
    | SkillSectionItem
    | CourseSectionItem
    | LanguageSectionItem
    | ReferenceSectionItem
    | LinkSectionItem
    | InternshipSectionItem
    | str
)


class ResumeSection(StrictBaseModel):
    title: str = ""
    type: str = ""
    items: str | list[SectionItem] = Field(default_factory=list)

    @field_validator("title", "type", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class ResumeData(StrictBaseModel):
    name: str = ""
    title: str = ""
    location: str = ""
    phone: str = ""
    email: str = ""
    summary: str = ""
    dateOfBirth: str = ""
    gender: str = ""
    nationality: str = ""
    documentDate: str = ""
    address: str = ""
    postalCode: str = ""
    secondaryAddress: str | None = None
    sections: list[ResumeSection] = Field(default_factory=list)

    @field_validator(
        "name",
        "title",
        "location",
        "phone",
        "email",
        "summary",
        "dateOfBirth",
        "gender",
        "nationality",
        "documentDate",
        "address",
        "postalCode",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        return normalize_optional_string(value)


class ResumeProfile(StrictBaseModel):
    data: ResumeData = Field(default_factory=ResumeData)


class ResumeParseResponse(StrictBaseModel):
    id: str
    profile: ResumeProfile
    metadata: dict[str, Any]
    resumeId: str | None = None
    version: int | None = None
    status: str | None = None


class ResumeRephraseRequest(StrictBaseModel):
    text: str = Field(min_length=1, max_length=8000)
    prompt: str | None = Field(default=None, max_length=4000)

    @field_validator("text", "prompt", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> str:
        return normalize_optional_string(value).strip()


class ResumeRephraseResponse(StrictBaseModel):
    rephrasedText: str = Field(min_length=1)

    @field_validator("rephrasedText", mode="before")
    @classmethod
    def normalize_rephrased_text(cls, value: Any) -> str:
        return normalize_optional_string(value).strip()
