import re
import unicodedata
from pathlib import Path, PurePath

from app.errors import EvidenceValidationError

MIME_BY_EXTENSION: dict[str, set[str]] = {
    ".eml": {"message/rfc822", "application/octet-stream", "text/plain"},
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xls": {"application/vnd.ms-excel", "application/octet-stream"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"},
    ".txt": {"text/plain"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
}
BLOCKED_EXTENSIONS = {".exe", ".sh", ".bat", ".cmd", ".ps1", ".com"}


def safe_filename(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name
    name = unicodedata.normalize("NFKC", name).strip().replace("\x00", "")
    stem = re.sub(r"[^\w.-]+", "_", Path(name).stem, flags=re.UNICODE).strip("._")
    suffix = Path(name).suffix.lower()
    if not stem:
        stem = "evidence"
    return f"{stem[:200]}{suffix}"


class FileValidator:
    def __init__(self, allowed_extensions: tuple[str, ...], max_size_bytes: int) -> None:
        self.allowed_extensions = {item.lower() for item in allowed_extensions}
        self.max_size_bytes = max_size_bytes

    def validate_metadata(self, filename: str | None, content_type: str | None) -> tuple[str, str]:
        if not filename:
            raise EvidenceValidationError("EVIDENCE_FILENAME_REQUIRED", "Filename is required")
        cleaned = safe_filename(filename)
        extension = Path(cleaned).suffix.lower()
        if extension in BLOCKED_EXTENSIONS or extension not in self.allowed_extensions:
            raise EvidenceValidationError("EVIDENCE_INVALID_TYPE", "Unsupported evidence file type")
        declared_type = (content_type or "application/octet-stream").lower().split(";", 1)[0]
        allowed_mimes = MIME_BY_EXTENSION.get(extension, {"application/octet-stream"})
        if declared_type not in allowed_mimes:
            raise EvidenceValidationError(
                "EVIDENCE_MIME_MISMATCH", "Declared MIME type does not match file extension"
            )
        return cleaned, extension

    def validate_size(self, size: int) -> None:
        if size <= 0:
            raise EvidenceValidationError("EVIDENCE_EMPTY", "Evidence file is empty")
        if size > self.max_size_bytes:
            raise EvidenceValidationError("EVIDENCE_TOO_LARGE", "Evidence file is too large")
