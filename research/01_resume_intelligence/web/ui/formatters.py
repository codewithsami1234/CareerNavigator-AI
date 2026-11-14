"""Display helpers that do not rescore or invent fields."""
from __future__ import annotations

import json
from functools import lru_cache

import config


def file_size_label(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    if num < 1024 * 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num / (1024 * 1024):.1f} MB"


@lru_cache(maxsize=1)
def taxonomy_summary() -> str:
    """Count the taxonomy file. This is not a model accuracy figure."""
    try:
        data = json.loads(config.SKILLS_TAXONOMY_PATH.read_text(encoding="utf-8"))
        categories = data.get("categories") or {}
        if not isinstance(categories, dict):
            return ""
        skill_count = sum(len(items) for items in categories.values() if isinstance(items, list))
    except (OSError, json.JSONDecodeError, TypeError):
        return ""
    return (
        f"The local skill taxonomy lists {skill_count} skills in {len(categories)} categories. "
        "Matching uses these names and aliases. It is not a trained model."
    )
