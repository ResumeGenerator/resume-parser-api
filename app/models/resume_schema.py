from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OnlineProfile(StrictBaseModel):
    platform: str = ""
    url: str = ""


class CandidateProfile(StrictBaseModel):
    fullName: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    currentTitle: str = ""
    professionalHeadline: str = ""
    totalExperienceYears: float | None = None
    targetRole: str | None = None
    securityClearance: str | None = None
    visaStatusOrWorkAuthorization: str | None = None
    onlineProfiles: list[OnlineProfile] = Field(default_factory=list)


class CareerClassification(StrictBaseModel):
    industry: str = ""
    jobFamily: str = ""
    subSpecialization: str = ""
    seniorityLevel: str = ""


class CareerProgression(StrictBaseModel):
    careerLevel: str = ""
    industryFocus: list[str] = Field(default_factory=list)
    primarySpecialization: list[str] = Field(default_factory=list)
    secondarySpecialization: list[str] = Field(default_factory=list)


class CoreSkills(StrictBaseModel):
    hardSkills: list[str] = Field(default_factory=list)
    toolsAndSoftware: list[str] = Field(default_factory=list)
    methodologiesAndFrameworks: list[str] = Field(default_factory=list)
    industryKnowledge: list[str] = Field(default_factory=list)
    softSkills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class SkillsMatrix(StrictBaseModel):
    programmingLanguages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    cloudPlatforms: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    devOpsTools: list[str] = Field(default_factory=list)
    testingTools: list[str] = Field(default_factory=list)
    businessTools: list[str] = Field(default_factory=list)
    industryTools: list[str] = Field(default_factory=list)


class WorkExperienceItem(StrictBaseModel):
    companyOrOrganization: str = ""
    role: str = ""
    location: str = ""
    startDate: str | None = None
    endDate: str | None = None
    isCurrent: bool = False
    employmentType: str | None = None
    managementLevel: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    toolsAndTaxonomiesUsed: list[str] = Field(default_factory=list)
    keywordsExtracted: list[str] = Field(default_factory=list)
    industryOrDomain: str = ""


class ProjectOrCaseStudy(StrictBaseModel):
    name: str = ""
    projectType: str = ""
    associatedCompany: str | None = None
    clientOrStakeholder: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    description: str = ""
    role: str = ""
    technologies: list[str] = Field(default_factory=list)
    toolsAndMethodologiesUsed: list[str] = Field(default_factory=list)
    keyContributions: list[str] = Field(default_factory=list)
    businessOutcome: str = ""
    measurableImpact: str = ""


class Achievement(StrictBaseModel):
    achievement: str = ""
    category: str = ""
    sourceCompany: str = ""
    year: int | None = None


class EducationItem(StrictBaseModel):
    degree: str = ""
    majorOrFieldOfStudy: str = ""
    institution: str = ""
    location: str = ""
    endDate: str | None = None
    gpa: str | float | None = None
    honors: list[str] = Field(default_factory=list)


class CertificationOrLicense(StrictBaseModel):
    name: str = ""
    issuer: str | None = None
    year: int | None = None
    isActive: bool | None = None


class KeywordDensityItem(StrictBaseModel):
    keyword: str = ""
    count: int | None = None


class ResumeBlocks(StrictBaseModel):
    executiveSummary: list[str] = Field(default_factory=list)
    technicalHighlights: list[str] = Field(default_factory=list)
    leadershipHighlights: list[str] = Field(default_factory=list)
    projectHighlights: list[str] = Field(default_factory=list)
    industryHighlights: list[str] = Field(default_factory=list)


class RecommendedResumeVariant(StrictBaseModel):
    name: str = ""
    confidence: float | None = None


class AtsAnalysis(StrictBaseModel):
    estimatedAtsScore: int | None = Field(default=None, ge=0, le=100)
    keywordDensity: list[str | KeywordDensityItem] = Field(default_factory=list)
    missingCriticalSections: list[str] = Field(default_factory=list)
    formattingRisks: list[str] = Field(default_factory=list)
    duplicateSkills: list[str] = Field(default_factory=list)


class JobFitAnalysis(StrictBaseModel):
    matchPercentage: int | None = Field(default=None, ge=0, le=100)
    strongMatches: list[str] = Field(default_factory=list)
    partialMatches: list[str] = Field(default_factory=list)
    missingRequirements: list[str] = Field(default_factory=list)


class ResumeGenerationStrategy(StrictBaseModel):
    standardAtsVersion: list[str] = Field(default_factory=list)
    performanceAndMetricsDrivenVersion: list[str] = Field(default_factory=list)
    leadershipOrSpecialistVersion: list[str] = Field(default_factory=list)
    functionalOrCareerChangeVersion: list[str] = Field(default_factory=list)


class SafeRewriteSuggestion(StrictBaseModel):
    category: str = ""
    originalPoint: str = ""
    improvedPoint: str = ""
    reason: str = ""


class ResumeProfile(StrictBaseModel):
    candidateProfile: CandidateProfile = Field(default_factory=CandidateProfile)
    careerClassification: CareerClassification = Field(default_factory=CareerClassification)
    careerProgression: CareerProgression = Field(default_factory=CareerProgression)
    professionalSummaryPoints: list[str] = Field(default_factory=list)
    coreSkills: CoreSkills = Field(default_factory=CoreSkills)
    skillsMatrix: SkillsMatrix = Field(default_factory=SkillsMatrix)
    workExperience: list[WorkExperienceItem] = Field(default_factory=list)
    projectsOrCaseStudies: list[ProjectOrCaseStudy] = Field(default_factory=list)
    achievementBank: list[Achievement] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certificationsAndLicenses: list[CertificationOrLicense] = Field(default_factory=list)
    affiliationsAndMemberships: list[str] = Field(default_factory=list)
    awardsAndRecognition: list[str] = Field(default_factory=list)
    volunteerExperience: list[str] = Field(default_factory=list)
    publicationsAndSpeaking: list[str] = Field(default_factory=list)
    resumeBlocks: ResumeBlocks = Field(default_factory=ResumeBlocks)
    recommendedResumeVariants: list[RecommendedResumeVariant] = Field(default_factory=list)
    atsAnalysis: AtsAnalysis = Field(default_factory=AtsAnalysis)
    jobFitAnalysis: JobFitAnalysis = Field(default_factory=JobFitAnalysis)
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
