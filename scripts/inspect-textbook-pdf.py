#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.textbook_pdf_parser import (
    TextbookOutlineInspector,
    TextbookPdfParser,
    rj_junior_math_grade7_vol1_chapter1_patterns,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a textbook PDF and generate a chapter outline draft."
    )
    parser.add_argument("--pdf", required=True, help="Path to the textbook PDF.")
    parser.add_argument("--output", required=True, help="Output YAML or JSON path.")
    parser.add_argument(
        "--preset",
        choices=["rj-junior-math-grade7-vol1-chapter1"],
        default="rj-junior-math-grade7-vol1-chapter1",
        help="Known textbook/chapter inspection preset.",
    )
    parser.add_argument("--max-pages", type=int, default=None, help="Optional page limit.")
    parser.add_argument("--format", choices=["yaml", "json"], default="yaml")
    args = parser.parse_args()

    pages = TextbookPdfParser().extract_pages(Path(args.pdf), max_pages=args.max_pages)
    outline = TextbookOutlineInspector().inspect(
        pages,
        textbook=_textbook_metadata(args.pdf),
        chapter_id="ch1",
        chapter_title="第一章",
        section_patterns=rj_junior_math_grade7_vol1_chapter1_patterns(),
    )
    _write(Path(args.output), outline, args.format)
    print(
        f"Inspected {args.pdf}: {outline['pdf_inspection']['page_count']} pages, "
        f"wrote {args.output}"
    )
    return 0


def _textbook_metadata(pdf_path: str) -> dict[str, Any]:
    return {
        "source_id": "textbook-rj-math-grade7-vol1",
        "textbook_id": "rj-junior-math-grade7-vol1",
        "title": "人教版初中数学七年级上册",
        "publisher": "人民教育出版社",
        "edition": "authorized_local_copy",
        "subject": "数学",
        "grade": "七年级",
        "volume": "上册",
        "path_or_uri": pdf_path,
        "copyright_policy": "authorized_use",
        "manifest_copyright_policy": "authorized_use",
        "parse_status": "pdf_outline_candidate",
    }


def _write(path: Path, payload: dict[str, Any], output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        if output_format == "json":
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        else:
            yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    raise SystemExit(main())
