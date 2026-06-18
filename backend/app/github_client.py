"""Thin async client around the public GitHub REST API.

Only the two endpoints we need are implemented:
  * list a user's public repositories
  * fetch a repository's README (raw text)

No token is required for public data, but if a ``GITHUB_TOKEN`` is supplied
it is used to raise the rate limit (60 -> 5000 requests/hour).
"""

from __future__ import annotations

import re

import httpx

GITHUB_API = "https://api.github.com"


class GitHubError(Exception):
    """Generic GitHub failure (rate limit, server error, ...)."""


class UserNotFoundError(GitHubError):
    """The requested GitHub user does not exist."""


def parse_username(raw: str) -> str:
    """Accept a bare username, an ``@handle`` or a full profile URL.

    >>> parse_username("https://github.com/torvalds")
    'torvalds'
    >>> parse_username("@torvalds")
    'torvalds'
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Username is required")

    # Pull the handle out of a profile URL if one was pasted.
    match = re.search(r"github\.com/([^/\s?#]+)", raw)
    if match:
        return match.group(1)

    return raw.lstrip("@")


def _headers(token: str | None, raw: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
        "User-Agent": "github-profile-reviewer",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def fetch_repos(
    client: httpx.AsyncClient, username: str, token: str | None = None
) -> list[dict]:
    """Return the user's public, owned repositories (most recently pushed first)."""
    resp = await client.get(
        f"{GITHUB_API}/users/{username}/repos",
        params={"per_page": 100, "sort": "pushed", "type": "owner"},
        headers=_headers(token),
    )

    if resp.status_code == 404:
        raise UserNotFoundError(f"GitHub user '{username}' was not found")
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise GitHubError(
            "GitHub API rate limit exceeded. Set a GITHUB_TOKEN to raise the limit."
        )
    resp.raise_for_status()
    return resp.json()


async def fetch_readme(
    client: httpx.AsyncClient, full_name: str, token: str | None = None
) -> str | None:
    """Return the raw README text for ``owner/repo``, or ``None`` if there is none."""
    resp = await client.get(
        f"{GITHUB_API}/repos/{full_name}/readme",
        headers=_headers(token, raw=True),
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.text
