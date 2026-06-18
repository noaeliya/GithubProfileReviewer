"""FastAPI application exposing a single profile-review endpoint."""

from __future__ import annotations

import asyncio
import os

import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .ai import assess_repo
from .github_client import (
    GitHubError,
    UserNotFoundError,
    fetch_readme,
    fetch_repos,
    parse_username,
)
from .models import RepoAssessment, ReviewResponse

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # optional, raises rate limit

app = FastAPI(
    title="GitHub Profile Reviewer",
    description="Fetches a user's repos, reads each README and rates it with Claude.",
    version="1.0.0",
)

# The React dev server runs on a different port, so allow it through CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_anthropic() -> AsyncAnthropic:
    """Build the Claude client, failing loudly if the key is missing."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
        )
    return AsyncAnthropic(api_key=api_key)


@app.get("/api/health")
async def health() -> dict[str, bool]:
    """Simple liveness check; also reports whether the AI key is configured."""
    return {"ok": True, "ai_configured": bool(os.getenv("ANTHROPIC_API_KEY"))}


async def _review_one(
    http_client: httpx.AsyncClient,
    ai_client: AsyncAnthropic,
    repo: dict,
) -> RepoAssessment:
    """Fetch one repo's README and get its AI assessment."""
    readme = await fetch_readme(http_client, repo["full_name"], GITHUB_TOKEN)
    verdict = await assess_repo(
        ai_client,
        repo=repo["name"],
        description=repo.get("description"),
        language=repo.get("language"),
        readme=readme,
    )
    return RepoAssessment(
        repo=repo["name"],
        description=repo.get("description"),
        language=repo.get("language"),
        stars=repo.get("stargazers_count", 0),
        url=repo.get("html_url", ""),
        has_readme=readme is not None,
        **verdict,
    )


@app.get("/api/review", response_model=ReviewResponse)
async def review(
    username: str = Query(..., description="GitHub username or profile URL"),
    limit: int = Query(10, ge=1, le=30, description="Max repositories to review"),
) -> ReviewResponse:
    """Review a GitHub profile: list repos, read READMEs, assess each with Claude."""
    try:
        user = parse_username(username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ai_client = _get_anthropic()

    async with httpx.AsyncClient(timeout=30) as http_client:
        try:
            repos = await fetch_repos(http_client, user, GITHUB_TOKEN)
        except UserNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GitHubError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        if not repos:
            return ReviewResponse(
                username=user,
                profile_url=f"https://github.com/{user}",
                repo_count=0,
                reviewed_count=0,
                results=[],
            )

        # Most-recently-pushed repos first; cap the work so big profiles stay fast.
        selected = repos[:limit]

        results = await asyncio.gather(
            *(_review_one(http_client, ai_client, repo) for repo in selected)
        )

    return ReviewResponse(
        username=user,
        profile_url=f"https://github.com/{user}",
        repo_count=len(repos),
        reviewed_count=len(results),
        results=list(results),
    )
