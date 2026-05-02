class RagService:
    """Boundary for retrieval-augmented generation storage.

    This is a placeholder until we decide whether to use pgvector, a vector DB,
    file-backed search, or another hybrid approach.
    """

    def retrieve(self, query: str) -> str:
        return "当前样板知识库：初中数学一元一次方程"


def get_rag_service() -> RagService:
    return RagService()
