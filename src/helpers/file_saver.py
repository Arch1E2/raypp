from pathlib import Path
from typing import Any, List, Dict
from uuid import uuid4
import os

from src.core.config import settings


class FileSaver:
    def __init__(self, request=None, media_root: str | None = None):
        self.request = request
        self.media_root = media_root or settings.MEDIA_ROOT
        Path(self.media_root).mkdir(parents=True, exist_ok=True)

    async def save_all(self) -> List[Dict[str, Any]]:
        """Read files from request.form() and save them to disk. Returns list of metadata dicts."""
        if self.request is None:
            return []
        data = await self.request.form()
        files = []
        for key, value in data.items():
            # value can be UploadFile or str
            if hasattr(value, "filename"):
                files.append((key, value))
        saved = []
        for key, upload in files:
            saved.append(self.save_single(upload))
        return saved

    def save_single(self, upload) -> Dict[str, Any]:
        filename = upload.filename or f"file-{uuid4().hex}"
        dest = Path(self.media_root) / filename
        # read bytes and write
        content = upload.file.read() if hasattr(upload, "file") else upload
        if isinstance(content, str):
            content = content.encode("utf-8")
        dest.write_bytes(content)
        return {"field": getattr(upload, "name", "file"), "filename": filename, "path": str(dest), "content_type": getattr(upload, "content_type", None)}