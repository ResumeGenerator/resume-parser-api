from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateProfile(StrictBaseModel):
    fullName: str | None = None
    headline: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    location: str | None = None
    linkedinUrl: HttpUrl | None = None
    portfolioUrl: HttpUrl | None = None
    githubUrl: HttpUrl | None = None
    otherLinks: list[HttpUrl] = Field(default_factory=list)


class CareerClassification(StrictBaseModel):
    primaryFunction: str | None = None
    industries: list[str] = Field(default_factory=list)
    seniorityLevel: str | None = None
    yearsOfExperience: float | None = None
    targetRoles: list[str] = Field(default_factory=list)
    employmentTypeSignals: list[str] = Field(default_factory=list)


class CareerProgressionItem(StrictBaseModel):
    stage: str | None = None
    title: str | None = None
    company: str | None = None
    timeframe: str | None = None
    summary: str | None = None


class SkillEvidence(StrictBaseModel):
    skill: str
    evidence: list[str] = Field(default_factory=list)
    proficiencySignal: str | None = None


class SkillsMatrix(StrictBaseModel):
    technicalSkills: list[SkillEvidence] = Field(default_factory=list)
    domainSkills: list[SkillEvidence] = Field(default_factory=list)
    toolsAndPlatforms: list[SkillEvidence] = Field(default_factory=list)
    leadershipAndSoftSkills: list[SkillEvidence] = Field(default_factory=list)
    languages: list[SkillEvidence] = Field(default_factory=list)


class DateRange(StrictBaseModel):
    start: str | None = None
    end: str | None = None
    isCurrent: bool = False


class WorkExperienceItem(StrictBaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    dateRange: DateRange = Field(default_factory=DateRange)
    description: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    atsKeywords: list[str] = Field(default_factory=list)


class ProjectOrCaseStudy(StrictBaseModel):
    name: str | None = None
    role: str | None = None
    context: str | None = None
    problem: str | None = None
    actions: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    links: list[HttpUrl] = Field(default_factory=list)


class Achievement(StrictBaseModel):
    text: str
    category: str | None = None
    sourceRole: str | None = None
    quantified: bool = False
    metrics: list[str] = Field(default_factory=list)
    rewritePotential: Literal["low", "medium", "high"] | None = None


class EducationItem(StrictBaseModel):
    institution: str | None = None
    degree: str | None = None
    fieldOfStudy: str | None = None
    location: str | None = None
    dateRange: DateRange = Field(default_factory=DateRange)
    honors: list[str] = Field(default_factory=list)
    coursework: list[str] = Field(default_factory=list)


class CertificationOrLicense(StrictBaseModel):
    name: str | None = None
    issuer: str | None = None
    issuedDate: str | None = None
    expirationDate: str | None = None
    credentialId: str | None = None
    credentialUrl: HttpUrl | None = None


class SimpleDatedItem(StrictBaseModel):
    title: str | None = None
    organization: str | None = None
    date: str | None = None
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)


class PublicationOrSpeaking(StrictBaseModel):
    title: str | None = None
    venue: str | None = None
    date: str | None = None
    url: HttpUrl | None = None
    description: str | None = None


class ResumeBlocks(StrictBaseModel):
    headlineOptions: list[str] = Field(default_factory=list)
    summaryBlock: list[str] = Field(default_factory=list)
    skillsBlock: list[str] = Field(default_factory=list)
    experienceBlocks: list[str] = Field(default_factory=list)
    projectBlocks: list[str] = Field(default_factory=list)
    educationBlock: list[str] = Field(default_factory=list)
    certificationBlock: list[str] = Field(default_factory=list)


class RecommendedResumeVariant(StrictBaseModel):
    variantName: str
    targetRole: str | None = None
    positioning: str | None = None
    sectionsToEmphasize: list[str] = Field(default_factory=list)
    keywordsToInclude: list[str] = Field(default_factory=list)


class AtsAnalysis(StrictBaseModel):
    overallScore: int | None = Field(default=None, ge=0, le=100)
    parseReadiness: str | None = None
    formattingRisks: list[str] = Field(default_factory=list)
    keywordCoverage: list[str] = Field(default_factory=list)
    sectionCompleteness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class JobFitAnalysis(StrictBaseModel):
    fitScore: int | None = Field(default=None, ge=0, le=100)
    matchedRequirements: list[str] = Field(default_factory=list)
    partialMatches: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    positioningAdvice: list[str] = Field(default_factory=list)


class ResumeGenerationStrategy(StrictBaseModel):
    targetNarrative: str | None = None
    prioritySections: list[str] = Field(default_factory=list)
    tone: str | None = None
    contentRules: list[str] = Field(default_factory=list)
    rewriteFocusAreas: list[str] = Field(default_factory=list)
    atsOptimizationPlan: list[str] = Field(default_factory=list)


class SafeRewriteSuggestion(StrictBaseModel):
    originalText: str | None = None
    suggestedRewrite: str
    rationale: str | None = None
    confidence: Literal["low", "medium", "high"] | None = None


class ResumeProfile(StrictBaseModel):
    candidateProfile: CandidateProfile = Field(default_factory=CandidateProfile)
    careerClassification: CareerClassification = Field(default_factory=CareerClassification)
    careerProgression: list[CareerProgressionItem] = Field(default_factory=list)
    professionalSummaryPoints: list[str] = Field(default_factory=list)
    coreSkills: list[str] = Field(default_factory=list)
    skillsMatrix: SkillsMatrix = Field(default_factory=SkillsMatrix)
    workExperience: list[WorkExperienceItem] = Field(default_factory=list)
    projectsOrCaseStudies: list[ProjectOrCaseStudy] = Field(default_factory=list)
    achievementBank: list[Achievement] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certificationsAndLicenses: list[CertificationOrLicense] = Field(default_factory=list)
    affiliationsAndMemberships: list[SimpleDatedItem] = Field(default_factory=list)
    awardsAndRecognition: list[SimpleDatedItem] = Field(default_factory=list)
    volunteerExperience: list[SimpleDatedItem] = Field(default_factory=list)
    publicationsAndSpeaking: list[PublicationOrSpeaking] = Field(default_factory=list)
    resumeBlocks: ResumeBlocks = Field(default_factory=ResumeBlocks)
    recommendedResumeVariants: list[RecommendedResumeVariant] = Field(default_factory=list)
    atsAnalysis: AtsAnalysis = Field(default_factory=AtsAnalysis)
    jobFitAnalysis: JobFitAnalysis | None = None
    resumeStrengths: list[str] = Field(default_factory=list)
    missingOrWeakAreas: list[str] = Field(default_factory=list)
    atsKeywordsFound: list[str] = Field(default_factory=list)
    jobDescriptionKeywordMatches: list[str] = Field(default_factory=list)
    jobDescriptionKeywordGaps: list[str] = Field(default_factory=list)
    resumeGenerationStrategy: ResumeGenerationStrategy = Field(default_factory=ResumeGenerationStrategy)
    safeRewriteSuggestions: list[SafeRewriteSuggestion] = Field(default_factory=list)


class ResumeParseResponse(StrictBaseModel):
    profile: ResumeProfile
    metadata: dict[str, Any]

