"""Claude-powered assessment of a repository's README.

We keep one focused prompt that returns a small, strict JSON object so the
backend can stay simple and the frontend gets predictable fields.
"""

from __future__ import annotations

import json

from anthropic import AsyncAnthropic

# Haiku is cheap + fast and more than enough to judge a README.
MODEL = "claude-haiku-4-5"

# Cap how much README we send — keeps token cost low and avoids huge payloads.
MAX_README_CHARS = 6000

SYSTEM_PROMPT = (
    "You are a senior engineer reviewing a developer's public GitHub repository. "
    "Given the repo metadata and its README, judge the project's level and how "
    "clear the README is. Be concise, fair, and concrete. "
    "Reply with ONLY a JSON object (no markdown, no prose) with exactly these keys:\n"
    '  "level": one of "Basic", "Intermediate", "Advanced"\n'
    '  "readme_clarity": one of "Missing", "Poor", "Fair", "Good", "Excellent"\n'
    '  "assessment": 1-3 sentences summarising complexity, README quality, and the '
    "experience level it reflects."
)


def _build_user_message(
    repo: str, description: str | None, language: str | None, readme: str | None
) -> str:
    parts = [
        f"Repository: {repo}",
        f"Primary language: {language or 'unknown'}",
        f"Description: {description or '(none)'}",
        "",
    ]
    if readme:
        parts.append("README:")
        parts.append(readme[:MAX_README_CHARS])
    else:
        parts.append("README: (this repository has no README file)")
    return "\n".join(parts)


def _fallback(reason: str) -> dict[str, str]:
    """Used when the AI call fails or returns something unparseable."""
    return {
        "level": "Unknown",
        "readme_clarity": "Unknown",
        "assessment": f"Could not generate an AI assessment ({reason}).",
    }


async def assess_repo(
    client: AsyncAnthropic,
    repo: str,
    description: str | None,
    language: str | None,
    readme: str | None,
) -> dict[str, str]:
    """Return ``{level, readme_clarity, assessment}`` for one repository.

    Never raises — on any failure it returns a safe fallback so one bad repo
    can't crash the whole review.
    """
    try:
        message = await client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _build_user_message(repo, description, language, readme),
                },
                # Prefill the assistant turn with "{" to coax clean JSON.
                {"role": "assistant", "content": "{"},
            ],
        )
        raw = "{" + message.content[0].text
        data = json.loads(raw)
        return {
            "level": str(data.get("level", "Unknown")),
            "readme_clarity": str(data.get("readme_clarity", "Unknown")),
            "assessment": str(data.get("assessment", "")).strip(),
        }
    except json.JSONDecodeError:
        return _fallback("invalid AI response")
    except Exception as exc:  # noqa: BLE001 - we deliberately degrade gracefully
        return _fallback(type(exc).__name__)
