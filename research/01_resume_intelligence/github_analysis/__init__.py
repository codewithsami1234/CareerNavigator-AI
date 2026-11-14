"""Public GitHub metadata analysis. Network access stays inside this package."""

from .analyze import analyze_github, clear_github_cache

__all__ = ["analyze_github", "clear_github_cache"]
