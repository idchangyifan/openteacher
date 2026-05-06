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


@dataclass(frozen=True)
class RagTurnContext:
    query: str
    current_chapter_id: str = ""
    current_section_id: str = ""
    current_knowledge_point_id: str = ""
    current_skill_id: str = ""
    teaching_mode: str = ""
    learner_state: str = ""
    next_teacher_goal: str = ""
    current_question: str = ""
    student_answer_status: str = ""
    recent_messages: list[str] = field(default_factory=list)

    @property
    def preferred_teaching_phases(self) -> list[str]:
        if self.student_answer_status in {
            "incorrect_symbol",
            "incorrect_sign",
            "stuck",
        }:
            return ["correction", "explanation", "diagnosis"]
        if self.student_answer_status == "correct":
            return ["practice", "assessment", "summary"]
        if self.teaching_mode in {"active_lesson", "diagnostic_check"}:
            return ["opening", "diagnosis", "planning"]
        if self.teaching_mode == "adaptive_remediation":
            return ["correction", "explanation"]
        if self.teaching_mode == "guided_practice":
            return ["practice", "explanation", "correction"]
        if self.teaching_mode == "concept_instruction":
            return ["explanation", "diagnosis"]
        if self.teaching_mode == "lesson_summary":
            return ["summary", "assessment"]
        if self.teaching_mode == "review":
            return ["assessment", "summary", "practice"]
        return []

    @property
    def preferred_content_types(self) -> list[str]:
        if self.student_answer_status in {"incorrect_symbol", "incorrect_sign"}:
            return ["error_contrast", "correction_strategy", "misconception"]
        if self.student_answer_status == "stuck":
            return ["worked_example_step", "correction_strategy", "worked_example"]
        if self.student_answer_status == "correct":
            return ["variant_problem", "mastery_check", "lesson_summary"]
        if self.teaching_mode in {"active_lesson", "diagnostic_check"}:
            return ["lesson_opening", "diagnostic_question", "learning_objectives"]
        if self.teaching_mode == "adaptive_remediation":
            return ["error_contrast", "correction_strategy", "worked_example_step"]
        if self.teaching_mode == "guided_practice":
            return ["variant_problem", "practice_sequence", "worked_example_step"]
        if self.teaching_mode == "concept_instruction":
            return ["concept_summary", "worked_example", "diagnostic_question"]
        if self.teaching_mode == "lesson_summary":
            return ["lesson_summary", "mastery_check"]
        if self.teaching_mode == "review":
            return ["mastery_check", "lesson_summary", "variant_problem"]
        return []


@dataclass(frozen=True)
class RankedRagChunk:
    chunk: RagChunk
    score: int
    route_hits: list[str]


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

    def retrieve_for_turn(self, context: RagTurnContext) -> str:
        return self.retrieve(context.query)


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
        return self.retrieve_for_turn(RagTurnContext(query=query))

    def retrieve_for_turn(self, context: RagTurnContext) -> str:
        chunks = self._load_chunks()
        if not chunks:
            return "教材 RAG 暂无可用 chunks。"

        scored = [
            (self._score(context, chunk), index, chunk) for index, chunk in enumerate(chunks)
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

    def _score(self, context: RagTurnContext, chunk: RagChunk) -> int:
        haystack = (
            f"{chunk.id} {chunk.content_type} {chunk.chapter_id} "
            f"{chunk.source_section_id} {chunk.teaching_phase} {chunk.difficulty} "
            f"{' '.join(chunk.knowledge_point_ids)} "
            f"{' '.join(chunk.retrieval_tags)} "
            f"{' '.join(chunk.student_error_pattern_ids)} {chunk.text}"
        ).lower()
        tokens = self._tokens(context.query)
        score = sum(2 for token in tokens if token in haystack)
        score += _rerank_metadata_score(context, chunk)
        return score

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
        return self.retrieve_for_turn(RagTurnContext(query=query))

    def retrieve_for_turn(self, context: RagTurnContext) -> str:
        ranked = self._find_ranked_chunks(context)
        if not ranked:
            return "MongoDB 教材 RAG 暂无可用 chunks。"

        lines = ["MongoDB 教材 RAG 检索结果（多路召回 + rerank）："]
        for item in ranked:
            chunk = item.chunk
            knowledge_points = "、".join(chunk.knowledge_point_ids) or "未标注知识点"
            routes = "、".join(item.route_hits) or "fallback"
            lines.append(
                "- "
                f"[{chunk.id}] {chunk.content_type} / {chunk.teaching_phase or 'unknown_phase'} "
                f"/ {chunk.chapter_id} / {knowledge_points} / score={item.score} / routes={routes}："
                f"{chunk.text}"
            )
        return "\n".join(lines)

    def _default_collection(self) -> Any:
        client = MongoClient(settings.mongodb_uri)
        return client[settings.mongodb_database]["textbook_chunks"]

    def _find_ranked_chunks(self, context: RagTurnContext) -> list[RankedRagChunk]:
        candidates: dict[str, tuple[dict[str, Any], set[str]]] = {}
        for route in self._routes(context):
            for doc in self._find_route_docs(route["filter"]):
                chunk_id = str(doc.get("id") or "")
                if not chunk_id:
                    continue
                existing = candidates.get(chunk_id)
                if existing is None:
                    candidates[chunk_id] = (doc, {route["name"]})
                else:
                    existing[1].add(route["name"])

        if not candidates:
            for doc in self._find_route_docs({}):
                chunk_id = str(doc.get("id") or "")
                if chunk_id:
                    candidates[chunk_id] = (doc, {"fallback"})

        ranked: list[RankedRagChunk] = []
        for doc, route_hits in candidates.values():
            chunk = self._chunk_from_doc(doc)
            if chunk is None:
                continue
            score = self._score(context, chunk, route_hits)
            if score <= 0:
                continue
            ranked.append(
                RankedRagChunk(
                    chunk=chunk,
                    score=score,
                    route_hits=sorted(route_hits),
                )
            )

        ranked.sort(key=lambda item: (-item.score, item.chunk.id))
        return ranked[: self.max_chunks]

    def _find_route_docs(self, filter_doc: dict[str, Any]) -> list[dict[str, Any]]:
        return list(
            self.collection.find(
                filter_doc,
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
            ).limit(80)
        )

    def _routes(self, context: RagTurnContext) -> list[dict[str, Any]]:
        tokens = self._tokens(context.query)
        routes: list[dict[str, Any]] = []
        if context.current_knowledge_point_id:
            routes.append(
                {
                    "name": "knowledge_point",
                    "filter": {"knowledge_point_ids": context.current_knowledge_point_id},
                }
            )
        if context.current_section_id:
            routes.append(
                {
                    "name": "section",
                    "filter": {"source_section_id": context.current_section_id},
                }
            )
        if context.current_chapter_id:
            routes.append(
                {
                    "name": "chapter",
                    "filter": {"chapter_id": context.current_chapter_id},
                }
            )
        if context.preferred_teaching_phases:
            routes.append(
                {
                    "name": "teaching_phase",
                    "filter": {"teaching_phase": {"$in": context.preferred_teaching_phases}},
                }
            )
        if context.preferred_content_types:
            routes.append(
                {
                    "name": "content_type",
                    "filter": {"content_type": {"$in": context.preferred_content_types}},
                }
            )
        tag_values = [
            *tokens,
            context.current_knowledge_point_id,
            context.current_section_id,
            *context.preferred_teaching_phases,
            *context.preferred_content_types,
        ]
        tag_values = [value for value in dict.fromkeys(tag_values) if value]
        if tag_values:
            routes.append(
                {
                    "name": "retrieval_tags",
                    "filter": {"retrieval_tags": {"$in": tag_values}},
                }
            )
        text_clauses = self._text_query_clauses(tokens)
        if text_clauses:
            routes.append({"name": "lexical_text", "filter": {"$or": text_clauses}})
        if context.student_answer_status in {"incorrect_symbol", "incorrect_sign", "stuck"}:
            routes.append(
                {
                    "name": "student_error_pattern",
                    "filter": {
                        "$or": [
                            {"student_error_pattern_ids.0": {"$exists": True}},
                            {
                                "content_type": {
                                    "$in": [
                                        "error_contrast",
                                        "misconception",
                                        "correction_strategy",
                                    ]
                                }
                            },
                        ]
                    },
                }
            )
        return routes

    def _text_query_clauses(self, tokens: list[str]) -> list[dict[str, Any]]:
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

    def _score(self, context: RagTurnContext, chunk: RagChunk, route_hits: set[str]) -> int:
        score = TextbookFileRagService(Path())._score(context, chunk)
        score += len(route_hits) * 4
        score += _rerank_metadata_score(context, chunk)
        return score

    def _tokens(self, query: str) -> list[str]:
        return TextbookFileRagService(Path())._tokens(query)


def get_rag_service() -> RagService:
    if settings.rag_backend == "textbook_file":
        return TextbookFileRagService(settings.textbook_rag_artifact_path)
    if settings.rag_backend == "mongodb":
        return MongoTextbookRagService()
    return RagService()


def _rerank_metadata_score(context: RagTurnContext, chunk: RagChunk) -> int:
    score = 0
    if context.current_knowledge_point_id in chunk.knowledge_point_ids:
        score += 30
    if context.current_section_id and context.current_section_id == chunk.source_section_id:
        score += 18
    if context.current_chapter_id and context.current_chapter_id == chunk.chapter_id:
        score += 8
    if chunk.teaching_phase in context.preferred_teaching_phases:
        score += 16
    if chunk.content_type in context.preferred_content_types:
        score += 20
    if context.current_knowledge_point_id and context.current_knowledge_point_id in chunk.retrieval_tags:
        score += 10
    if context.current_section_id and context.current_section_id in chunk.retrieval_tags:
        score += 6
    if context.student_answer_status in {"incorrect_symbol", "incorrect_sign", "stuck"}:
        if chunk.student_error_pattern_ids:
            score += 15
        if chunk.content_type in {"error_contrast", "correction_strategy", "misconception"}:
            score += 12
    if context.student_answer_status == "correct" and chunk.content_type in {
        "variant_problem",
        "mastery_check",
        "lesson_summary",
    }:
        score += 15
    return score
