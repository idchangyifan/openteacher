from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TextbookPdfParserError(RuntimeError):
    """Raised when a textbook PDF cannot be parsed."""


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class SectionPattern:
    id: str
    title: str
    keywords: list[str]
    order: int
    knowledge_point_ids: list[str]


class TextbookPdfParser:
    def extract_pages(self, pdf_path: Path, *, max_pages: int | None = None) -> list[PdfPageText]:
        if not pdf_path.exists():
            raise TextbookPdfParserError(f"PDF not found: {pdf_path}")

        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise TextbookPdfParserError("pypdf is required to parse textbook PDFs") from exc

        reader = PdfReader(str(pdf_path))
        pages: list[PdfPageText] = []
        page_limit = len(reader.pages) if max_pages is None else min(max_pages, len(reader.pages))
        for index in range(page_limit):
            raw_text = reader.pages[index].extract_text() or ""
            pages.append(PdfPageText(page_number=index + 1, text=_normalize_text(raw_text)))
        return pages


class TextbookOutlineInspector:
    """Build a chapter outline draft from extracted PDF text.

    The first version uses known section keywords and page occurrence candidates.
    Human review is still expected before certification, but it replaces blank
    page ranges with evidence-bearing candidates from the actual PDF.
    """

    def inspect(
        self,
        pages: list[PdfPageText],
        *,
        textbook: dict[str, Any],
        chapter_id: str,
        chapter_title: str,
        section_patterns: list[SectionPattern],
    ) -> dict[str, Any]:
        sorted_patterns = sorted(section_patterns, key=lambda pattern: pattern.order)
        matches: dict[str, int | None] = {}
        min_page = 1
        for pattern in sorted_patterns:
            match = self._find_first_page(pages, pattern.keywords, min_page=min_page)
            matches[pattern.id] = match
            if match is not None:
                min_page = match + 1

        sections = []
        for index, pattern in enumerate(sorted_patterns):
            start = matches[pattern.id]
            next_starts = [
                matches[next_pattern.id]
                for next_pattern in sorted_patterns[index + 1 :]
                if matches[next_pattern.id] is not None
            ]
            end = (min(next_starts) - 1) if start is not None and next_starts else None
            sections.append(
                {
                    "id": pattern.id,
                    "title": pattern.title,
                    "order": pattern.order,
                    "page_range": {"start": start, "end": end},
                    "knowledge_point_ids": pattern.knowledge_point_ids,
                    "match_keywords": pattern.keywords,
                }
            )

        chapter_starts = [section["page_range"]["start"] for section in sections]
        known_starts = [value for value in chapter_starts if value is not None]
        chapter_start = min(known_starts) if known_starts else None
        chapter_end_candidates = [section["page_range"]["end"] for section in sections]
        known_ends = [value for value in chapter_end_candidates if value is not None]
        chapter_end = max(known_ends) if known_ends else None

        return {
            "textbook": textbook,
            "pdf_inspection": {
                "page_count": len(pages),
                "parser": "pypdf",
                "review_status": "needs_review",
            },
            "chapters": [
                {
                    "id": chapter_id,
                    "title": chapter_title,
                    "order": 1,
                    "page_range": {"start": chapter_start, "end": chapter_end},
                    "sections": sections,
                }
            ],
        }

    def _find_first_page(
        self, pages: list[PdfPageText], keywords: list[str], *, min_page: int = 1
    ) -> int | None:
        for page in pages:
            if page.page_number < min_page:
                continue
            text = page.text
            if all(self._matches_keyword(text, keyword) for keyword in keywords):
                return page.page_number
        return None

    def _matches_keyword(self, text: str, keyword: str) -> bool:
        if keyword.startswith("re:"):
            return re.search(keyword[3:], text) is not None
        return keyword in text


def rj_junior_math_grade7_vol1_chapter1_patterns() -> list[SectionPattern]:
    return [
        SectionPattern(
            id="ch1-sec1",
            title="正数和负数",
            keywords=["正数", "负数"],
            order=1,
            knowledge_point_ids=["kp-positive-negative-numbers"],
        ),
        SectionPattern(
            id="ch1-sec2",
            title="有理数",
            keywords=["有理数"],
            order=2,
            knowledge_point_ids=["kp-rational-number-classification"],
        ),
        SectionPattern(
            id="ch1-sec3",
            title="数轴",
            keywords=["数轴"],
            order=3,
            knowledge_point_ids=["kp-number-line"],
        ),
        SectionPattern(
            id="ch1-sec4",
            title="相反数",
            keywords=["相反数"],
            order=4,
            knowledge_point_ids=["kp-opposite-numbers"],
        ),
        SectionPattern(
            id="ch1-sec5",
            title="绝对值",
            keywords=["绝对值"],
            order=5,
            knowledge_point_ids=["kp-absolute-value"],
        ),
        SectionPattern(
            id="ch1-sec6",
            title="有理数的加减法",
            keywords=["有理数的加法"],
            order=6,
            knowledge_point_ids=["kp-rational-add-subtract"],
        ),
        SectionPattern(
            id="ch1-sec7",
            title="有理数的乘除法",
            keywords=["有理数的乘法"],
            order=7,
            knowledge_point_ids=["kp-rational-multiply-divide"],
        ),
        SectionPattern(
            id="ch1-sec8",
            title="有理数的乘方",
            keywords=["有理数的乘方"],
            order=8,
            knowledge_point_ids=["kp-rational-powers"],
        ),
        SectionPattern(
            id="ch1-sec9",
            title="科学记数法与近似数",
            keywords=["科学记数法"],
            order=9,
            knowledge_point_ids=["kp-scientific-notation", "kp-approximation"],
        ),
        SectionPattern(
            id="ch1-review",
            title="小结与复习",
            keywords=["小结"],
            order=10,
            knowledge_point_ids=[],
        ),
    ]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)
