from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


class RagService:
    """Boundary for retrieval-augmented generation storage.

    This is a placeholder until we decide whether to use pgvector, a vector DB,
    file-backed search, or another hybrid approach.
    """

    def retrieve(self, query: str) -> str:
        return "当前样板知识库：初中数学一元一次方程"


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
                f"[{chunk.id}] {chunk.content_type} / {chunk.chapter_id} / {knowledge_points}："
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
                )
            )
        return chunks

    def _score(self, query: str, chunk: RagChunk) -> int:
        haystack = (
            f"{chunk.id} {chunk.content_type} {chunk.chapter_id} "
            f"{' '.join(chunk.knowledge_point_ids)} {chunk.text}"
        ).lower()
        tokens = self._tokens(query)
        return sum(1 for token in tokens if token in haystack)

    def _tokens(self, query: str) -> list[str]:
        normalized = query.lower().strip()
        tokens = [token for token in normalized.replace("，", " ").replace("。", " ").split() if token]
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
        ]:
            if keyword in query:
                tokens.append(keyword.lower())
        return list(dict.fromkeys(tokens))


def get_rag_service() -> RagService:
    if settings.rag_backend == "textbook_file":
        return TextbookFileRagService(settings.textbook_rag_artifact_path)
    return RagService()
