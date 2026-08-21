"""解析安全限制：阻止 Office 压缩包膨胀及异常大的结构化文档耗尽 Worker 资源。"""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from app.errors import EvidenceValidationError

MAX_TEXT_CHARACTERS = 10_000_000
MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_EXPANDED_BYTES = 500 * 1024 * 1024
MAX_ARCHIVE_RATIO = 200
MAX_SPREADSHEET_SHEETS = 100
MAX_SPREADSHEET_ROWS = 100_000
MAX_SPREADSHEET_CELLS = 1_000_000
MAX_PDF_PAGES = 2_000
MAX_WORD_PARAGRAPHS = 200_000


def validate_zip_container(source: Path) -> None:
    try:
        with ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_FILES:
                raise EvidenceValidationError(
                    "ARCHIVE_FILE_LIMIT", "Office document contains too many archive members"
                )
            expanded = sum(item.file_size for item in members)
            compressed = sum(item.compress_size for item in members)
            if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
                raise EvidenceValidationError(
                    "ARCHIVE_EXPANDED_SIZE_LIMIT", "Office document expands beyond safety limit"
                )
            if expanded and expanded / max(compressed, 1) > MAX_ARCHIVE_RATIO:
                raise EvidenceValidationError(
                    "ARCHIVE_RATIO_LIMIT", "Office document has an unsafe compression ratio"
                )
            if any(item.flag_bits & 0x1 for item in members):
                raise EvidenceValidationError(
                    "ARCHIVE_ENCRYPTED", "Encrypted Office documents are not supported"
                )
    except BadZipFile as exc:
        raise EvidenceValidationError(
            "OFFICE_CONTAINER_INVALID", "Office document container is invalid"
        ) from exc
