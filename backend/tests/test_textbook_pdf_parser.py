from app.services.textbook_pdf_parser import (
    PdfPageText,
    TextbookOutlineInspector,
    rj_junior_math_grade7_vol1_chapter1_patterns,
)


def test_textbook_outline_inspector_finds_section_page_candidates() -> None:
    pages = [
        PdfPageText(page_number=1, text="封面"),
        PdfPageText(page_number=2, text="目录第一章有理数"),
        PdfPageText(page_number=3, text="1.1正数和负数收入支出温度"),
        PdfPageText(page_number=8, text="1.2有理数整数分数"),
        PdfPageText(page_number=12, text="数轴上的点"),
        PdfPageText(page_number=16, text="相反数"),
        PdfPageText(page_number=20, text="绝对值"),
    ]

    outline = TextbookOutlineInspector().inspect(
        pages,
        textbook={"textbook_id": "rj-junior-math-grade7-vol1"},
        chapter_id="ch1",
        chapter_title="第一章",
        section_patterns=rj_junior_math_grade7_vol1_chapter1_patterns(),
    )

    chapter = outline["chapters"][0]
    sections = {section["id"]: section for section in chapter["sections"]}

    assert outline["pdf_inspection"]["page_count"] == 7
    assert outline["pdf_inspection"]["review_status"] == "needs_review"
    assert chapter["page_range"]["start"] == 3
    assert sections["ch1-sec1"]["page_range"] == {"start": 3, "end": 7}
    assert sections["ch1-sec2"]["page_range"] == {"start": 8, "end": 11}
    assert sections["ch1-sec5"]["page_range"] == {"start": 20, "end": None}


def test_textbook_outline_inspector_keeps_missing_matches_reviewable() -> None:
    pages = [PdfPageText(page_number=1, text="只有正数和负数")]

    outline = TextbookOutlineInspector().inspect(
        pages,
        textbook={"textbook_id": "rj-junior-math-grade7-vol1"},
        chapter_id="ch1",
        chapter_title="第一章",
        section_patterns=rj_junior_math_grade7_vol1_chapter1_patterns(),
    )

    sections = {section["id"]: section for section in outline["chapters"][0]["sections"]}

    assert sections["ch1-sec1"]["page_range"]["start"] == 1
    assert sections["ch1-sec2"]["page_range"]["start"] is None
    assert outline["pdf_inspection"]["review_status"] == "needs_review"
