"""End-to-end tests for the /api/review endpoint.

GitHub is mocked with respx and the Claude call is monkeypatched, so these
tests run offline and for free.
"""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import main
from app.github_client import GITHUB_API


@pytest.fixture
def client(monkeypatch):
    # A dummy key so _get_anthropic() doesn't reject the request.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    # Replace the real Claude call with a deterministic stub.
    async def fake_assess(ai_client, repo, description, language, readme):
        return {
            "level": "Basic",
            "readme_clarity": "Good" if readme else "Missing",
            "assessment": f"Stub assessment for {repo}.",
        }

    monkeypatch.setattr(main, "assess_repo", fake_assess)
    return TestClient(main.app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@respx.mock
def test_review_success(client):
    respx.get(f"{GITHUB_API}/users/octocat/repos").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "hello",
                    "full_name": "octocat/hello",
                    "description": "demo",
                    "language": "Python",
                    "stargazers_count": 3,
                    "html_url": "https://github.com/octocat/hello",
                }
            ],
        )
    )
    respx.get(f"{GITHUB_API}/repos/octocat/hello/readme").mock(
        return_value=httpx.Response(200, text="# Hello")
    )

    resp = client.get("/api/review", params={"username": "octocat"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "octocat"
    assert body["reviewed_count"] == 1
    assert body["results"][0]["repo"] == "hello"
    assert body["results"][0]["has_readme"] is True
    assert body["results"][0]["level"] == "Basic"


@respx.mock
def test_review_user_not_found(client):
    respx.get(f"{GITHUB_API}/users/ghost/repos").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    resp = client.get("/api/review", params={"username": "ghost"})
    assert resp.status_code == 404


@respx.mock
def test_review_repo_without_readme(client):
    respx.get(f"{GITHUB_API}/users/octocat/repos").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "empty",
                    "full_name": "octocat/empty",
                    "description": None,
                    "language": None,
                    "stargazers_count": 0,
                    "html_url": "https://github.com/octocat/empty",
                }
            ],
        )
    )
    respx.get(f"{GITHUB_API}/repos/octocat/empty/readme").mock(
        return_value=httpx.Response(404)
    )

    resp = client.get("/api/review", params={"username": "octocat"})
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["has_readme"] is False
    assert result["readme_clarity"] == "Missing"


def test_review_missing_key_returns_500(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    local_client = TestClient(main.app, raise_server_exceptions=False)
    resp = local_client.get("/api/review", params={"username": "octocat"})
    assert resp.status_code == 500
