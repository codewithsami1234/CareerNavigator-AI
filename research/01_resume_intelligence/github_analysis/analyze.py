"""Read a public GitHub profile and a bounded set of public repositories.

The client calls ``https://api.github.com`` only. A token is optional, comes
from the ``GITHUB_TOKEN`` environment variable or an explicit argument, and is
never written into results. Tests pass a fake transport so the suite does not
use the network.

Repository language lists, topics, descriptions, and README text are observed
evidence. Star counts, fork counts, and commit totals are not treated as
proficiency, ownership, or employment.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple
from urllib.parse import quote, urlparse

import config
from extractors.skill_extractor import SkillExtractor
from schemas import STATUS_FAILED, STATUS_SUCCESS, Section

_PROFILE_HOSTS = {"github.com", "www.github.com"}
_USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_RESERVED = {
    "about", "account", "explore", "features", "login", "logout", "marketplace",
    "new", "notifications", "orgs", "organizations", "pricing", "settings",
    "sponsors", "topics",
}
_CACHE: Dict[str, Tuple[float, int, Any, Dict[str, str]]] = {}


@dataclass
class GitHubSkillEvidence:
    """One observed skill mention. ``observed`` is always true for stored rows."""

    skill_name: str
    repository: str
    repository_url: str
    source_field: str
    text: str
    observed: bool = True
    note: Optional[str] = None


@dataclass
class GitHubRepository:
    name: str
    url: str
    description: Optional[str] = None
    languages: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    readme_excerpt: Optional[str] = None
    pushed_at: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class GitHubAnalysis:
    """Public-profile reading. No proficiency and no employability score."""

    status: str = STATUS_FAILED
    username: Optional[str] = None
    profile_url: Optional[str] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    public_repos: Optional[int] = None
    repositories: List[GitHubRepository] = field(default_factory=list)
    skills: List[GitHubSkillEvidence] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class Transport(Protocol):
    def request(self, url: str, headers: Dict[str, str]) -> Tuple[int, Any, Dict[str, str]]:
        """Return ``(status, json_or_text, response_headers)``."""


def clear_github_cache() -> None:
    _CACHE.clear()


def normalize_github_login(value: str) -> str:
    """Return a login, or raise ``ValueError`` with a user-facing reason."""
    text = (value or "").strip()
    if not text or any(ch.isspace() for ch in text):
        raise ValueError("Enter a GitHub username or a public profile URL.")
    if "://" in text or "github.com" in text.lower():
        parsed = urlparse(text if "://" in text else f"https://{text}")
        host = (parsed.hostname or "").lower()
        if host not in _PROFILE_HOSTS:
            raise ValueError("Only a github.com profile URL or a username is accepted.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 1:
            raise ValueError("Enter a profile URL such as https://github.com/username, not a repository URL.")
        login = parts[0]
    else:
        login = text[1:] if text.startswith("@") else text
    if not _USER_RE.match(login) or login.lower() in _RESERVED:
        raise ValueError("That does not look like a public GitHub username.")
    return login


def _redact(message: str, token: Optional[str]) -> str:
    if token and token in message:
        return message.replace(token, "[token]")
    return message


class UrllibTransport:
    """HTTPS client limited to api.github.com."""

    def request(self, url: str, headers: Dict[str, str]) -> Tuple[int, Any, Dict[str, str]]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "api.github.com":
            raise ValueError("Only the public GitHub API is requested.")
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=config.GITHUB_TIMEOUT_SECONDS) as response:
                raw = response.read()
                header_map = {key.lower(): value for key, value in response.headers.items()}
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read() if exc.fp is not None else b""
            header_map = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
            status = exc.code
        text = raw.decode("utf-8", errors="replace")
        if "application/json" in header_map.get("content-type", "") or text[:1] in "{[":
            try:
                body: Any = json.loads(text) if text else {}
            except json.JSONDecodeError:
                body = text
        else:
            body = text
        return status, body, header_map


def _headers(token: Optional[str], *, raw: bool = False) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
        "User-Agent": "CareerNavigator-AI-research",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _cached_request(
    transport: Transport,
    url: str,
    headers: Dict[str, str],
    *,
    clock: Callable[[], float],
    token: Optional[str],
) -> Tuple[int, Any, Dict[str, str]]:
    now = clock()
    cached = _CACHE.get(url)
    if cached and now - cached[0] < config.GITHUB_CACHE_SECONDS:
        return cached[1], cached[2], cached[3]
    try:
        status, body, response_headers = transport.request(url, headers)
    except TimeoutError as exc:
        detail = _redact(str(exc), token)
        raise TimeoutError(
            "GitHub did not respond in time. Check the network connection and try again. "
            f"The GitHub request timed out: {detail}"
        ) from exc
    except OSError as exc:
        detail = _redact(f"{exc.__class__.__name__}: {exc}", token)
        raise OSError(
            "GitHub could not be reached. Check the network connection and try again. "
            f"The GitHub request failed: {detail}"
        ) from exc
    if status == 200:
        _CACHE[url] = (now, status, body, response_headers)
    return status, body, response_headers


def _rate_limited(status: int, body: Any, headers: Dict[str, str]) -> bool:
    if status == 429:
        return True
    remaining = headers.get("x-ratelimit-remaining")
    if status == 403 and remaining == "0":
        return True
    if status == 403 and isinstance(body, dict) and "rate limit" in str(body.get("message", "")).lower():
        return True
    return False


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _skills_from(
    extractor: SkillExtractor,
    text: str,
    *,
    repository: str,
    repository_url: str,
    source_field: str,
    section_name: str,
    note: Optional[str],
) -> List[GitHubSkillEvidence]:
    if not text or not text.strip():
        return []
    found = extractor.extract([Section(
        name=section_name, heading=None, start_line=0, end_line=0, content=text,
    )])
    rows: List[GitHubSkillEvidence] = []
    for skill in found:
        evidence = skill.evidence[0].text if skill.evidence else text
        rows.append(GitHubSkillEvidence(
            skill_name=skill.name,
            repository=repository,
            repository_url=repository_url,
            source_field=source_field,
            text=_clip(evidence, config.EVIDENCE_TEXT_MAX_CHARS),
            observed=True,
            note=note,
        ))
    return rows


def _failed(reason: str, *, token: Optional[str] = None, username: Optional[str] = None) -> GitHubAnalysis:
    safe = _redact(reason, token)
    return GitHubAnalysis(
        status=STATUS_FAILED, username=username, reason=safe, errors=[safe],
        limitations=_limitations(),
    )


def _limitations() -> List[str]:
    return [
        "Only public GitHub API data is read. Private repositories are skipped.",
        "Language lists, topics, descriptions, and README text are observed evidence.",
        "Stars, forks, and commit counts are not treated as proficiency, ownership, or employment.",
        f"At most {config.GITHUB_MAX_REPOS} recently pushed non-fork repositories are read.",
    ]


def analyze_github(
    username_or_url: str,
    *,
    token: Optional[str] = None,
    transport: Optional[Transport] = None,
    clock: Optional[Callable[[], float]] = None,
) -> GitHubAnalysis:
    """Analyze a public profile. ``transport`` is for tests; the default uses urllib."""
    supplied = token if token is not None else os.environ.get("GITHUB_TOKEN") or None
    if supplied is not None and not str(supplied).strip():
        supplied = None
    try:
        login = normalize_github_login(username_or_url if isinstance(username_or_url, str) else "")
    except ValueError as exc:
        return _failed(str(exc), token=supplied)
    client = transport or UrllibTransport()
    now = clock or time.time
    base = config.GITHUB_API_BASE.rstrip("/")
    user_url = f"{base}/users/{quote(login)}"
    try:
        status, body, headers = _cached_request(
            client, user_url, _headers(supplied), clock=now, token=supplied,
        )
    except (TimeoutError, OSError, ValueError) as exc:
        return _failed(str(exc), token=supplied, username=login)
    if _rate_limited(status, body, headers):
        reason = "GitHub rate limit was reached. Wait and try again, or set GITHUB_TOKEN in the environment."
        return GitHubAnalysis(
            status="rate_limited", username=login, profile_url=f"https://github.com/{login}",
            reason=reason, errors=[reason], limitations=_limitations(),
        )
    if status == 404:
        return _failed(f"No public GitHub user named {login} was found.", token=supplied, username=login)
    if status != 200 or not isinstance(body, dict):
        return _failed(
            f"GitHub returned status {status} for the profile, so it was not analyzed.",
            token=supplied, username=login,
        )
    result = GitHubAnalysis(
        status=STATUS_SUCCESS,
        username=login,
        profile_url=body.get("html_url") or f"https://github.com/{login}",
        name=body.get("name") if isinstance(body.get("name"), str) else None,
        bio=body.get("bio") if isinstance(body.get("bio"), str) else None,
        public_repos=body.get("public_repos") if isinstance(body.get("public_repos"), int) else None,
        limitations=_limitations(),
    )
    repos_url = f"{base}/users/{quote(login)}/repos?per_page=100&type=owner&sort=pushed"
    try:
        repo_status, repo_body, repo_headers = _cached_request(
            client, repos_url, _headers(supplied), clock=now, token=supplied,
        )
    except (TimeoutError, OSError, ValueError) as exc:
        result.warnings.append(_redact(str(exc), supplied))
        result.reason = "The profile was read, but the repository list could not be retrieved."
        return result
    if _rate_limited(repo_status, repo_body, repo_headers):
        result.warnings.append("GitHub rate limit was reached while listing repositories.")
        result.reason = result.warnings[-1]
        return result
    if repo_status != 200 or not isinstance(repo_body, list):
        result.warnings.append(f"GitHub returned status {repo_status} for the repository list.")
        return result

    selected = [
        repo for repo in repo_body
        if isinstance(repo, dict) and not repo.get("private") and not repo.get("fork") and repo.get("name")
    ]
    skipped_private = sum(1 for repo in repo_body if isinstance(repo, dict) and repo.get("private"))
    skipped_forks = sum(1 for repo in repo_body if isinstance(repo, dict) and repo.get("fork") and not repo.get("private"))
    if skipped_private:
        result.warnings.append("Private repositories were skipped.")
    if skipped_forks:
        result.warnings.append("Forks were not analyzed.")
    selected = selected[: config.GITHUB_MAX_REPOS]
    extractor = SkillExtractor()
    language_note = "Present in the repository language list. This is not a proficiency level."
    for repo in selected:
        name = str(repo.get("name"))
        url = str(repo.get("html_url") or f"https://github.com/{login}/{name}")
        description = repo.get("description") if isinstance(repo.get("description"), str) else None
        topics = [str(topic) for topic in repo.get("topics") or [] if isinstance(topic, str)]
        pushed_at = repo.get("pushed_at") if isinstance(repo.get("pushed_at"), str) else None
        record = GitHubRepository(
            name=name, url=url, description=description, topics=topics, pushed_at=pushed_at,
        )
        owner = str(repo.get("full_name") or f"{login}/{name}")
        languages = _read_languages(client, base, owner, supplied, now, record)
        record.languages = languages
        readme = _read_readme(client, base, owner, supplied, now, record)
        record.readme_excerpt = _clip(readme, 500) if readme else None
        result.repositories.append(record)
        result.skills.extend(_skills_from(
            extractor, description or "", repository=name, repository_url=url,
            source_field="description", section_name="projects", note=None,
        ))
        result.skills.extend(_skills_from(
            extractor, ", ".join(topics), repository=name, repository_url=url,
            source_field="topics", section_name="skills", note=None,
        ))
        result.skills.extend(_skills_from(
            extractor, ", ".join(languages), repository=name, repository_url=url,
            source_field="languages", section_name="skills", note=language_note,
        ))
        result.skills.extend(_skills_from(
            extractor, (readme or "")[: config.GITHUB_README_SCAN_CHARS],
            repository=name, repository_url=url, source_field="readme",
            section_name="projects", note=None,
        ))
    if not selected:
        result.warnings.append("No public non-fork repositories were available to analyze.")
    return result


def _read_languages(client, base, full_name, token, clock, record: GitHubRepository) -> List[str]:
    url = f"{base}/repos/{quote(full_name, safe='/')}/languages"
    try:
        status, body, headers = _cached_request(client, url, _headers(token), clock=clock, token=token)
    except (TimeoutError, OSError, ValueError) as exc:
        record.warnings.append(_redact(str(exc), token))
        return []
    if _rate_limited(status, body, headers):
        record.warnings.append("GitHub rate limit was reached while reading languages.")
        return []
    if status == 404:
        record.warnings.append("Languages were not accessible for this repository.")
        return []
    if status != 200 or not isinstance(body, dict):
        record.warnings.append(f"Languages could not be read (status {status}).")
        return []
    return [str(name) for name in body.keys()]


def _read_readme(client, base, full_name, token, clock, record: GitHubRepository) -> Optional[str]:
    url = f"{base}/repos/{quote(full_name, safe='/')}/readme"
    try:
        status, body, headers = _cached_request(
            client, url, _headers(token, raw=True), clock=clock, token=token,
        )
    except (TimeoutError, OSError, ValueError) as exc:
        record.warnings.append(_redact(str(exc), token))
        return None
    if _rate_limited(status, body, headers):
        record.warnings.append("GitHub rate limit was reached while reading the README.")
        return None
    if status == 404:
        record.warnings.append("No README was accessible for this repository.")
        return None
    if status != 200 or not isinstance(body, str):
        record.warnings.append(f"The README could not be read (status {status}).")
        return None
    return body
