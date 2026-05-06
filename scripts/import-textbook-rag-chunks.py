#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml
from pymongo import MongoClient, UpdateOne


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import TextbookToTeachingSkill rag_chunks into MongoDB textbook_chunks."
    )
    parser.add_argument("--artifact", required=True, help="Pipeline artifact YAML path.")
    parser.add_argument("--mongodb-uri", default="mongodb://localhost:27017")
    parser.add_argument("--database", default="openteacher")
    parser.add_argument("--collection", default="textbook_chunks")
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    artifact = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(artifact, dict):
        raise SystemExit(f"Invalid pipeline artifact: {artifact_path}")

    client = MongoClient(args.mongodb_uri)
    collection = client[args.database][args.collection]
    result = import_chunks(collection, artifact)
    print(
        "Imported textbook chunks: "
        f"matched={result.matched_count} upserted={len(result.upserted_ids)} "
        f"modified={result.modified_count}"
    )


def import_chunks(collection: Any, artifact: dict[str, Any]) -> Any:
    operations = [
        UpdateOne(
            {"id": chunk["id"]},
            {"$set": _document_from_chunk(chunk, artifact)},
            upsert=True,
        )
        for chunk in artifact.get("rag_chunks", []) or []
        if _is_valid_chunk(chunk)
    ]
    _ensure_indexes(collection)
    if not operations:
        raise SystemExit("No valid rag_chunks found in artifact.")
    return collection.bulk_write(operations, ordered=False)


def _document_from_chunk(chunk: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    manifest = artifact.get("textbook_manifest") or {}
    page_range = chunk.get("page_range") or {}
    return {
        "id": str(chunk["id"]),
        "pipeline_id": str(artifact.get("pipeline_id") or ""),
        "pipeline_version": str(artifact.get("version") or ""),
        "textbook_id": str(manifest.get("textbook_id") or ""),
        "textbook_title": str(manifest.get("title") or ""),
        "source_ref": str(chunk.get("source_ref") or ""),
        "content_type": str(chunk.get("content_type") or "unknown"),
        "chapter_id": str(chunk.get("chapter_id") or ""),
        "knowledge_point_ids": [
            str(value) for value in chunk.get("knowledge_point_ids", []) or []
        ],
        "page_range": {
            "start": page_range.get("start"),
            "end": page_range.get("end"),
        },
        "text": str(chunk["text"]).strip(),
        "text_role": str(chunk.get("text_role") or ""),
        "review_status": str(chunk.get("review_status") or "draft"),
        "copyright_policy": str(chunk.get("copyright_policy") or ""),
    }


def _is_valid_chunk(chunk: object) -> bool:
    if not isinstance(chunk, dict):
        return False
    return bool(chunk.get("id") and isinstance(chunk.get("text"), str) and chunk["text"].strip())


def _ensure_indexes(collection: Any) -> None:
    collection.create_index("id", unique=True)
    collection.create_index("textbook_id")
    collection.create_index("chapter_id")
    collection.create_index("knowledge_point_ids")
    collection.create_index("content_type")
    collection.create_index("review_status")
    collection.create_index([("text", "text")], default_language="none")


if __name__ == "__main__":
    main()
