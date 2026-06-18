"""Pydantic models describing the API request/response shapes."""

from pydantic import BaseModel, Field


class RepoAssessment(BaseModel):
    """The AI assessment for a single repository, plus its GitHub metadata."""

    repo: str
    description: str | None = None
    language: str | None = None
    stars: int = 0
    url: str
    has_readme: bool

    # Filled in by the AI (see app.ai).
    level: str = Field(..., description="Basic | Intermediate | Advanced")
    readme_clarity: str = Field(..., description="Short verdict on README quality")
    assessment: str = Field(..., description="1-3 sentence human-readable summary")


class ReviewResponse(BaseModel):
    """Full response for a profile review."""

    username: str
    profile_url: str
    repo_count: int
    reviewed_count: int
    results: list[RepoAssessment]
