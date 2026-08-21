"""纯文本解析器：识别常见中文和 Unicode 编码，并对输出正文长度设置安全上限。"""

from pathlib import Path

from app.errors import EvidenceValidationError
from app.models.evidence import Evidence
from app.parsers.base import ParseResult
from app.parsers.limits import MAX_TEXT_CHARACTERS


def decode_text(content: bytes) -> tuple[str, str]:
    encodings = (
        ("utf-16", "utf-8-sig", "gb18030")
        if content.startswith((b"\xff\xfe", b"\xfe\xff"))
        else ("utf-8-sig", "gb18030")
    )
    for encoding in encodings:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise EvidenceValidationError("TEXT_ENCODING_UNSUPPORTED", "Text encoding is unsupported")


def ensure_text_limit(text: str) -> str:
    if len(text) > MAX_TEXT_CHARACTERS:
        raise EvidenceValidationError("TEXT_CONTENT_LIMIT", "Extracted text is too large")
    return text


class TextParser:
    name = "builtin-text"
    version = "1.0.0"

    def supports(self, evidence: Evidence) -> bool:
        return evidence.file_extension == ".txt"

    def parse(self, source: Path, evidence: Evidence) -> ParseResult:
        text, encoding = decode_text(source.read_bytes())
        return ParseResult(
            title=evidence.original_filename,
            text=ensure_text_limit(text),
            language=None,
            metadata={"encoding": encoding, "character_count": len(text)},
        )
