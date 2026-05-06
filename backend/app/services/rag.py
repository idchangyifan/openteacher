from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from pymongo import MongoClient
import yaml

from app.core.settings import settings


@dataclass(frozen=True)
class RagChunk:
    id: str
    source_ref: str
    content_type: str
    chapter_id: str
    knowledge_point_ids: list[str]
    text: str
    review_status: str
    source_section_id: str = ""
    teaching_phase: str = ""
    retrieval_tags: list[str] = field(default_factory=list)
    difficulty: str = ""
    student_error_pattern_ids: list[str] = field(default_factory=list)


class RagService:
    """Boundary for retrieval-augmented generation storage.

    This is a placeholder until we decide whether to use pgvector, a vector DB,
    file-backed search, or another hybrid approach.
    """

    def retrieve(self, query: str) -> str:
        return (
            "当前未启用真实教材 RAG；"
            "请优先依据已选择的 Teaching Skill 和课堂上下文授课。"
        )


class TextbookFileRagService:
    """File-backed RAG over TextbookToTeachingSkill pipeline artifacts.

    This intentionally uses lightweight lexical scoring for v1. The important
    contract is that teaching can retrieve traceable chunks before we choose a
    vector database.
    """

    def __init__(self, artifact_path: Path, max_chunks: int = 3) -> None:
        self.artifact_path = artifact_path
        self.max_chunks = max_chunks

    def retrieve(self, query: str) -> str:
        chunks = self._load_chunks()
        if not chunks:
            return "教材 RAG 暂无可用 chunks。"

        scored = [
            (self._score(query, chunk), index, chunk) for index, chunk in enumerate(chunks)
        ]
        matches = [
            chunk
            for score, _index, chunk in sorted(scored, key=lambda item: (-item[0], item[1]))
            if score > 0
        ][: self.max_chunks]
        if not matches:
            matches = chunks[: self.max_chunks]

        lines = ["教材 RAG 检索结果："]
        for chunk in matches:
            knowledge_points = "、".join(chunk.knowledge_point_ids) or "未标注知识点"
            lines.append(
                "- "
                f"[{chunk.id}] {chunk.content_type} / {chunk.teaching_phase or 'unknown_phase'} "
                f"/ {chunk.chapter_id} / {knowledge_points}："
                f"{chunk.text}"
            )
        return "\n".join(lines)

    def _load_chunks(self) -> list[RagChunk]:
        if not self.artifact_path.exists():
            return []

        with self.artifact_path.open(encoding="utf-8") as handle:
            artifact = yaml.safe_load(handle)
        if not isinstance(artifact, dict):
            return []

        chunks: list[RagChunk] = []
        for item in artifact.get("rag_chunks", []) or []:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            chunks.append(
                RagChunk(
                    id=str(item.get("id") or "unknown"),
                    source_ref=str(item.get("source_ref") or ""),
                    content_type=str(item.get("content_type") or "unknown"),
                    chapter_id=str(item.get("chapter_id") or ""),
                    knowledge_point_ids=[
                        str(value) for value in item.get("knowledge_point_ids", []) or []
                    ],
                    text=text.strip(),
                    review_status=str(item.get("review_status") or "draft"),
                    source_section_id=str(item.get("source_section_id") or ""),
                    teaching_phase=str(item.get("teaching_phase") or ""),
                    retrieval_tags=[
                        str(value) for value in item.get("retrieval_tags", []) or []
                    ],
                    difficulty=str(item.get("difficulty") or ""),
                    student_error_pattern_ids=[
                        str(value)
                        for value in item.get("student_error_pattern_ids", []) or []
                    ],
                )
            )
        return chunks

    def _score(self, query: str, chunk: RagChunk) -> int:
        haystack = (
            f"{chunk.id} {chunk.content_type} {chunk.chapter_id} "
            f"{chunk.source_section_id} {chunk.teaching_phase} {chunk.difficulty} "
            f"{' '.join(chunk.knowledge_point_ids)} "
            f"{' '.join(chunk.retrieval_tags)} "
            f"{' '.join(chunk.student_error_pattern_ids)} {chunk.text}"
        ).lower()
        tokens = self._tokens(query)
        return sum(1 for token in tokens if token in haystack)

    def _tokens(self, query: str) -> list[str]:
        normalized = query.lower().strip()
        tokens = [
            token
            for token in normalized.replace("，", " ").replace("。", " ").split()
            if token
        ]
        for keyword in [
            "正数",
            "负数",
            "有理数",
            "相反意义",
            "收入",
            "支出",
            "0",
            "概念",
            "情境",
            "数轴",
            "原点",
            "负号",
            "括号",
            "例题",
            "变式",
            "易错",
            "小结",
        ]:
            if keyword in query:
                tokens.append(keyword.lower())
        return list(dict.fromkeys(tokens))


class MongoTextbookRagService:
    """MongoDB-backed RAG over imported textbook chunks."""

    def __init__(
        self,
        collection: Any | None = None,
        *,
        max_chunks: int = 3,
    ) -> None:
        self.collection = collection or self._default_collection()
        self.max_chunks = max_chunks

    def retrieve(self, query: str) -> str:
        chunks = self._find_chunks(query)
        if not chunks:
            return "MongoDB 教材 RAG 暂无可用 chunks。"

        lines = ["MongoDB 教材 RAG 检索结果："]
        for chunk in chunks:
            knowledge_points = "、".join(chunk.knowledge_point_ids) or "未标注知识点"
            lines.append(
                "- "
                f"[{chunk.id}] {chunk.content_type} / {chunk.teaching_phase or 'unknown_phase'} "
                f"/ {chunk.chapter_id} / {knowledge_points}："
                f"{chunk.text}"
            )
        return "\n".join(lines)

    def _default_collection(self) -> Any:
        client = MongoClient(settings.mongodb_uri)
        return client[settings.mongodb_database]["textbook_chunks"]

    def _find_chunks(self, query: str) -> list[RagChunk]:
        tokens = self._tokens(query)
        clauses = self._query_clauses(tokens)
        raw_docs = list(
            self.collection.find(
                {"$or": clauses} if clauses else {},
                {
                    "_id": 0,
                    "id": 1,
                    "source_ref": 1,
                    "content_type": 1,
                    "chapter_id": 1,
                    "knowledge_point_ids": 1,
                    "source_section_id": 1,
                    "teaching_phase": 1,
                    "retrieval_tags": 1,
                    "difficulty": 1,
                    "student_error_pattern_ids": 1,
                    "text": 1,
                    "review_status": 1,
                },
            ).limit(50)
        )
        chunks = [chunk for chunk in (self._chunk_from_doc(doc) for doc in raw_docs) if chunk]
        scored = [
            (self._score(query, chunk), index, chunk) for index, chunk in enumerate(chunks)
        ]
        return [
            chunk
            for score, _index, chunk in sorted(scored, key=lambda item: (-item[0], item[1]))
            if score > 0
        ][: self.max_chunks]

    def _query_clauses(self, tokens: list[str]) -> list[dict[str, Any]]:
        clauses: list[dict[str, Any]] = []
        for token in tokens:
            if not token:
                continue
            escaped = re.escape(token)
            clauses.extend(
                [
                    {"text": {"$regex": escaped, "$options": "i"}},
                    {"content_type": {"$regex": escaped, "$options": "i"}},
                    {"teaching_phase": {"$regex": escaped, "$options": "i"}},
                    {"retrieval_tags": token},
                    {"source_section_id": token},
                    {"chapter_id": token},
                    {"knowledge_point_ids": token},
                ]
            )
        return clauses

    def _chunk_from_doc(self, doc: dict[str, Any]) -> RagChunk | None:
        text = doc.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        return RagChunk(
            id=str(doc.get("id") or "unknown"),
            source_ref=str(doc.get("source_ref") or ""),
            content_type=str(doc.get("content_type") or "unknown"),
            chapter_id=str(doc.get("chapter_id") or ""),
            knowledge_point_ids=[
                str(value) for value in doc.get("knowledge_point_ids", []) or []
            ],
            text=text.strip(),
            review_status=str(doc.get("review_status") or "draft"),
            source_section_id=str(doc.get("source_section_id") or ""),
            teaching_phase=str(doc.get("teaching_phase") or ""),
            retrieval_tags=[str(value) for value in doc.get("retrieval_tags", []) or []],
            difficulty=str(doc.get("difficulty") or ""),
            student_error_pattern_ids=[
                str(value) for value in doc.get("student_error_pattern_ids", []) or []
            ],
        )

    def _score(self, query: str, chunk: RagChunk) -> int:
        return TextbookFileRagService(Path())._score(query, chunk)

    def _tokens(self, query: str) -> list[str]:
        return TextbookFileRagService(Path())._tokens(query)


def get_rag_service() -> RagService:
    if settings.rag_backend == "textbook_file":
        return TextbookFileRagService(settings.textbook_rag_artifact_path)
    if settings.rag_backend == "mongodb":
        return MongoTextbookRagService()
    return RagService()
