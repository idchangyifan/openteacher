from __future__ import annotations

from collections.abc import Mapping

from deepagents.backends.protocol import BackendProtocol, FileDownloadResponse


class StaticMemoryBackend(BackendProtocol):
    """Read-only DeepAgents memory backend for OpenTeacher memory snapshots.

    DeepAgents `MemoryMiddleware` expects a backend that can download memory
    sources by path. OpenTeacher already keeps memory behind service boundaries
    and MongoDB-backed lesson history, so this backend exposes a generated
    snapshot as if it were an agent memory file without giving the model direct
    database access.
    """

    def __init__(self, files: Mapping[str, str]) -> None:
        self.files = dict(files)

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            content = self.files.get(path)
            if content is None:
                responses.append(FileDownloadResponse(path=path, error="file_not_found"))
                continue
            responses.append(
                FileDownloadResponse(
                    path=path,
                    content=content.encode("utf-8"),
                    error=None,
                )
            )
        return responses
