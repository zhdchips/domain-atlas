"""Deterministic local quality checks for URL source text."""

from __future__ import annotations

import re
from dataclasses import dataclass


TEMPLATE_MARKERS = (
    "skip to content",
    "navigation menu",
    "sign in",
    "sign up",
    "footer navigation",
    "cookie settings",
    "all rights reserved",
)


@dataclass(frozen=True)
class ContentQuality:
    accepted: bool
    text_characters: int
    template_marker_count: int
    reason: str

    def to_metadata(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "text_characters": self.text_characters,
            "template_marker_count": self.template_marker_count,
            "reason": self.reason,
        }


def assess_url_content(text: str) -> ContentQuality:
    normalized = " ".join(text.split())
    lowered = normalized.lower()
    marker_count = sum(lowered.count(marker) for marker in TEMPLATE_MARKERS)
    if len(normalized) < 180:
        return ContentQuality(
            accepted=False,
            text_characters=len(normalized),
            template_marker_count=marker_count,
            reason="可提取正文过短，无法作为可靠学习资料。",
        )
    if marker_count >= 4 and marker_count * 30 >= len(normalized):
        return ContentQuality(
            accepted=False,
            text_characters=len(normalized),
            template_marker_count=marker_count,
            reason="页面内容主要由导航、登录或页脚模板组成。",
        )
    return ContentQuality(
        accepted=True,
        text_characters=len(normalized),
        template_marker_count=marker_count,
        reason="正文质量满足自动摄取的最小要求。",
    )


def is_obvious_near_duplicate(left: str, right: str, *, threshold: float = 0.92) -> bool:
    """Detect exact or clearly overlapping text without a model/provider call."""
    left_normalized = _normalize_for_comparison(left)
    right_normalized = _normalize_for_comparison(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    left_shingles = _shingles(left_normalized)
    right_shingles = _shingles(right_normalized)
    if not left_shingles or not right_shingles:
        return False
    overlap = len(left_shingles & right_shingles) / min(len(left_shingles), len(right_shingles))
    return overlap >= threshold


def _normalize_for_comparison(text: str) -> str:
    return "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower()))


def _shingles(text: str) -> set[str]:
    width = 5
    if len(text) < width:
        return {text}
    return {text[index : index + width] for index in range(len(text) - width + 1)}
