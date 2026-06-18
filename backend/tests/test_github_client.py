"""Tests for the GitHub client: username parsing + the two HTTP calls (mocked)."""

import httpx
import pytest
import respx

from app.github_client import (
    GITHUB_API,
    UserNotFoundError,
    fetch_readme,
    fetch_repos,
    parse_username,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("torvalds", "torvalds"),
        ("@torvalds", "torvalds"),
        ("https://github.com/torvalds", "torvalds"),
        ("http://github.com/torvalds/", "torvalds"),
        ("  github.com/torvalds?tab=repositories ", "torvalds"),
    ],
)
def test_parse_username(raw, expected):
    assert parse_username(raw) == expected


def test_parse_username_empty_raises():
    with pytest.raises(ValueError):
        parse_username("   ")


@respx.mock
async def test_fetch_repos_success():
    respx.get(f"{GITHUB_API}/users/octocat/repos").mock(
        return_value=httpx.Response(200, json=[{"name": "hello"}])
    )
    async with httpx.AsyncClient() as client:
        repos = await fetch_repos(client, "octocat")
    assert repos == [{"name": "hello"}]


@respx.mock
async def test_fetch_repos_user_not_found():
    respx.get(f"{GITHUB_API}/users/ghost/repos").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(UserNotFoundError):
            await fetch_repos(client, "ghost")


@respx.mock
async def test_fetch_readme_returns_text():
    respx.get(f"{GITHUB_API}/repos/octocat/hello/readme").mock(
        return_value=httpx.Response(200, text="# Hello")
    )
    async with httpx.AsyncClient() as client:
        readme = await fetch_readme(client, "octocat/hello")
    assert readme == "# Hello"


@respx.mock
async def test_fetch_readme_missing_returns_none():
    respx.get(f"{GITHUB_API}/repos/octocat/empty/readme").mock(
        return_value=httpx.Response(404)
    )
    async with httpx.AsyncClient() as client:
        readme = await fetch_readme(client, "octocat/empty")
    assert readme is None
