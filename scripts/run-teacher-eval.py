#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = REPO_ROOT / "backend/tests/fixtures/teacher-core-golden.yaml"
DEFAULT_BASE_URL = os.environ.get("OPENTEACHER_API_BASE_URL", "http://127.0.0.1:8000/api/v1")

SUBJECT_LABELS = {
    "math": "数学",
    "chinese": "语文",
    "english": "英语",
    "physics": "物理",
    "general": "综合",
}

GRADE_LABELS = {
    "primary": "小学",
    "junior": "初一",
    "senior": "高一",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run OpenTeacher golden teacher-core cases against a live teacher chat API."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--teacher-style", default="严格但温暖")
    parser.add_argument("--dry-run", action="store_true", help="Write requests without calling the API.")
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError(f"Invalid teacher eval cases file: {path}")

    cases: list[dict[str, Any]] = []
    for item in payload["cases"]:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid case item in {path}")
        cases.append(item)
    return cases


def select_cases(
    cases: list[dict[str, Any]], case_ids: list[str], limit: int | None
) -> list[dict[str, Any]]:
    selected = cases
    if case_ids:
        wanted = set(case_ids)
        selected = [case for case in selected if case.get("id") in wanted]
        missing = wanted - {str(case.get("id")) for case in selected}
        if missing:
            raise ValueError(f"Unknown case id(s): {', '.join(sorted(missing))}")
    if limit is not None:
        selected = selected[:limit]
    return selected


def build_request(case: dict[str, Any], teacher_style: str) -> dict[str, Any]:
    subject = SUBJECT_LABELS.get(str(case["subject"]), str(case["subject"]))
    grade = GRADE_LABELS.get(str(case["grade"]), str(case["grade"]))
    return {
        "message": case["student_message"],
        "context": {
            "student_id": f"eval-{case['id']}",
            "grade": grade,
            "subject": subject,
            "teacher_style": teacher_style,
        },
    }


def call_teacher_api(base_url: str, request_payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/teacher/chat"
    body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_body = response.read().decode("utf-8")
    payload = json.loads(response_body)
    if not isinstance(payload, dict):
        raise ValueError("Teacher API response was not a JSON object")
    return payload


def default_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "reports" / f"teacher-core-eval-{timestamp}.jsonl"


def build_report_record(
    case: dict[str, Any],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None,
    error: str | None,
    elapsed_ms: int,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "subject": case["subject"],
        "grade": case["grade"],
        "knowledge_point": case["knowledge_point"],
        "learner_state": case["learner_state"],
        "student_message": case["student_message"],
        "expected_behaviors": case["expected_behaviors"],
        "forbidden_behaviors": case["forbidden_behaviors"],
        "ideal_teacher_move": case["ideal_teacher_move"],
        "scoring_notes": case["scoring_notes"],
        "request": request_payload,
        "response": response_payload,
        "error": error,
        "elapsed_ms": elapsed_ms,
        "dry_run": dry_run,
        "manual_score": None,
        "reviewer_notes": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_summary(output_path: Path, records: list[dict[str, Any]]) -> Path:
    summary_path = output_path.with_suffix(".summary.json")
    summary = {
        "report": str(output_path),
        "total_cases": len(records),
        "succeeded": sum(1 for record in records if record["response"] is not None),
        "failed": sum(1 for record in records if record["error"]),
        "dry_run": all(record["dry_run"] for record in records),
        "case_ids": [record["case_id"] for record in records],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary_path


def main() -> int:
    args = parse_args()
    output_path = args.output or default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cases = select_cases(load_cases(args.cases), args.case_id, args.limit)
    if not cases:
        print("No eval cases selected.", file=sys.stderr)
        return 2

    records: list[dict[str, Any]] = []
    with output_path.open("w", encoding="utf-8") as output_file:
        for index, case in enumerate(cases, start=1):
            request_payload = build_request(case, args.teacher_style)
            started = time.perf_counter()
            response_payload: dict[str, Any] | None = None
            error: str | None = None
            if not args.dry_run:
                try:
                    response_payload = call_teacher_api(args.base_url, request_payload, args.timeout)
                except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    error = f"{exc.__class__.__name__}: {exc}"
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            record = build_report_record(
                case=case,
                request_payload=request_payload,
                response_payload=response_payload,
                error=error,
                elapsed_ms=elapsed_ms,
                dry_run=args.dry_run,
            )
            records.append(record)
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            output_file.flush()

            status = "dry-run" if args.dry_run else ("ok" if error is None else "error")
            print(f"[{index}/{len(cases)}] {case['id']}: {status}")

    summary_path = write_summary(output_path, records)
    print(f"Report: {output_path}")
    print(f"Summary: {summary_path}")
    return 1 if any(record["error"] for record in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
