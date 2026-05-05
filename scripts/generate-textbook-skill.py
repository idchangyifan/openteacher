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

from app.services.textbook_to_skill_pipeline import build_textbook_to_skill_artifact


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a TextbookToTeachingSkill pipeline artifact from a structured draft."
    )
    parser.add_argument("--input", required=True, help="Input YAML or JSON draft path.")
    parser.add_argument("--output", required=True, help="Output YAML or JSON artifact path.")
    parser.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format. Defaults to yaml.",
    )
    args = parser.parse_args()

    source = _load_mapping(Path(args.input))
    artifact = build_textbook_to_skill_artifact(source)
    _write_artifact(Path(args.output), artifact, args.format)
    print(
        "Generated TextbookToTeachingSkill artifact: "
        f"{args.output} ({len(artifact['skill_drafts'])} skill drafts, "
        f"{len(artifact['rag_chunks'])} rag chunks)"
    )
    return 0


def _load_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        if path.suffix.lower() == ".json":
            data = json.load(handle)
        else:
            data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Input must be a mapping: {path}")
    return data


def _write_artifact(path: Path, artifact: dict[str, Any], output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        if output_format == "json":
            json.dump(artifact, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        else:
            yaml.safe_dump(artifact, handle, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    raise SystemExit(main())
