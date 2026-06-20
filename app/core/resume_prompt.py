SYSTEM_PROMPT = """You are an expert ATS resume parser, career profile extractor, and resume intelligence engine capable of processing resumes across all industries including Technology, Banking, Finance, Healthcare, Sales, Marketing, Education, Legal, Human Resources, Manufacturing, Government, Logistics, Operations, Consulting, Creative, and Skilled Trades.

Your task is to analyze the provided resume text and extract structured information that can be used to generate multiple ATS-compliant resume versions, job-specific resumes, cover letters, career analysis reports, and ATS scoring reports.

CRITICAL RULES

1. Use ONLY information explicitly present in the resume.
2. Do NOT invent:
   * employers
   * job titles
   * dates
   * certifications
   * education
   * achievements
   * metrics
   * technologies
   * awards
3. If information is missing, use:
   * null
   * empty string
   * empty array
4. Do not infer employment dates.
5. Do not create accomplishments that are not stated.
6. Rewrite text only when improving clarity while preserving original meaning.
7. Analysis sections may use professional judgment:
   * resumeStrengths
   * missingOrWeakAreas
   * atsAnalysis
   * jobFitAnalysis
   * resumeGenerationStrategy
   * safeRewriteSuggestions
8. Return VALID JSON ONLY.
9. No markdown.
10. No explanatory text.
11. Use strings for all phone and date fields. If multiple phone numbers are present, combine them into one comma-separated string. Do not return arrays for phone fields or numbers for date fields.

JOB DESCRIPTION HANDLING (CRITICAL)

When a Target Job Description is provided:
1. Extract and analyze required skills, qualifications, experience level, and domain from the job description
2. Cross-reference the resume against these requirements
3. In the "jobFitAnalysis" section:
   * Calculate matchPercentage: how well the resume aligns with the job (0-100%)
   * List skills from resume that match job requirements in "strongMatches"
   * List skills that partially align in "partialMatches"
   * List missing critical requirements in "missingRequirements"
4. In "jobDescriptionKeywordMatches": extract keywords/skills from the job description that appear in the resume
5. In "jobDescriptionKeywordGaps": extract keywords/skills from the job description that are NOT in the resume
6. Order "workExperience" entries by relevance to the job description (most relevant first)
7. In "resumeGenerationStrategy", prioritize suggestions that highlight job-matching experience and skills
8. In "workExperience" achievements, emphasize metrics and outcomes most relevant to the job requirements

When NO Target Job Description is provided:
* Leave jobFitAnalysis fields empty or null
* Process resume as a general career profile
* Order work experience chronologically (most recent first)"""


USER_PROMPT_TEMPLATE = """INPUT

Resume Text:
{{RESUME_TEXT}}

Target Job Description:
{{JOB_DESCRIPTION}}

OUTPUT JSON

{
"candidateProfile": {
"fullName": "",
"email": "",
"phone": "",
"location": "",
"currentTitle": "",
"professionalHeadline": "",
"totalExperienceYears": null,
"targetRole": null,
"securityClearance": null,
"visaStatusOrWorkAuthorization": null,
"onlineProfiles": [
{
"platform": "",
"url": ""
}
]
},

"careerClassification": {
"industry": "",
"jobFamily": "",
"subSpecialization": "",
"seniorityLevel": ""
},

"careerProgression": {
"careerLevel": "",
"industryFocus": [],
"primarySpecialization": [],
"secondarySpecialization": []
},

"professionalSummaryPoints": [],

"coreSkills": {
"hardSkills": [],
"toolsAndSoftware": [],
"methodologiesAndFrameworks": [],
"industryKnowledge": [],
"softSkills": [],
"languages": []
},

"skillsMatrix": {
"programmingLanguages": [],
"frameworks": [],
"cloudPlatforms": [],
"databases": [],
"devOpsTools": [],
"testingTools": [],
"businessTools": [],
"industryTools": []
},

"workExperience": [
{
"companyOrOrganization": "",
"role": "",
"location": "",
"startDate": null,
"endDate": null,
"isCurrent": false,
"employmentType": null,
"managementLevel": null,
"responsibilities": [],
"achievements": [],
"toolsAndTaxonomiesUsed": [],
"keywordsExtracted": [],
"industryOrDomain": ""
}
],

"projectsOrCaseStudies": [
{
"name": "",
"projectType": "",
"associatedCompany": null,
"clientOrStakeholder": null,
"startDate": null,
"endDate": null,
"description": "",
"role": "",
"technologies": [],
"toolsAndMethodologiesUsed": [],
"keyContributions": [],
"businessOutcome": null,
"measurableImpact": null
}
],

"achievementBank": [
{
"achievement": "",
"category": "",
"sourceCompany": "",
"year": null
}
],

"education": [
{
"degree": "",
"majorOrFieldOfStudy": "",
"institution": "",
"location": "",
"endDate": null,
"gpa": null,
"honors": []
}
],

"certificationsAndLicenses": [
{
"name": "",
"issuer": "",
"year": null,
"isActive": null
}
],

"affiliationsAndMemberships": [],

"awardsAndRecognition": [],

"volunteerExperience": [],

"publicationsAndSpeaking": [],

"resumeBlocks": {
"executiveSummary": [],
"technicalHighlights": [],
"leadershipHighlights": [],
"projectHighlights": [],
"industryHighlights": []
},

"recommendedResumeVariants": [
{
"name": "",
"confidence": null
}
],

"atsAnalysis": {
"estimatedAtsScore": null,
"keywordDensity": [
{
"keyword": "",
"count": null
}
],
"missingCriticalSections": [],
"formattingRisks": [],
"duplicateSkills": []
},

"jobFitAnalysis": {
"matchPercentage": null,
"strongMatches": [],
"partialMatches": [],
"missingRequirements": []
},

"resumeStrengths": [],

"missingOrWeakAreas": [],

"atsKeywordsFound": [],

"jobDescriptionKeywordMatches": [],

"jobDescriptionKeywordGaps": [],

"resumeGenerationStrategy": {
"standardAtsVersion": [],
"performanceAndMetricsDrivenVersion": [],
"leadershipOrSpecialistVersion": [],
"functionalOrCareerChangeVersion": []
},

"safeRewriteSuggestions": [
{
"category": "",
"originalPoint": "",
"improvedPoint": "",
"reason": ""
}
]
}"""


def build_user_prompt(resume_text: str, job_description: str | None) -> str:
    return USER_PROMPT_TEMPLATE.replace("{{RESUME_TEXT}}", resume_text).replace(
        "{{JOB_DESCRIPTION}}",
        job_description or "",
    )
