"""EML 解析器：提取邮件头、纯文本正文和附件，不执行附件或直接渲染不可信 HTML。"""

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import cast

from app.errors import EvidenceValidationError
from app.models.evidence import Evidence
from app.parsers.base import ParsedAttachment, ParseResult
from app.security.file_validation import safe_filename


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if value := data.strip():
            self.parts.append(value)


def _body_text(message: EmailMessage) -> str:
    preferred: str | None = None
    fallback: str | None = None
    parts = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        try:
            content = cast(EmailMessage, part).get_content()
        except (LookupError, UnicodeError):
            raw_payload = part.get_payload(decode=True)
            content = (
                raw_payload.decode("utf-8", errors="replace")
                if isinstance(raw_payload, bytes)
                else str(raw_payload)
            )
        if not isinstance(content, str):
            continue
        if content_type == "text/plain" and preferred is None:
            preferred = content
        elif content_type == "text/html" and fallback is None:
            extractor = _TextExtractor()
            extractor.feed(content)
            fallback = "\n".join(extractor.parts)
    return (preferred or fallback or "").strip()


class EmlParser:
    name = "stdlib-eml"
    version = "1.0.0"

    def __init__(self, max_attachments: int = 100, max_attachment_bytes: int = 100 * 1024 * 1024):
        self.max_attachments = max_attachments
        self.max_attachment_bytes = max_attachment_bytes

    def supports(self, evidence: Evidence) -> bool:
        return evidence.file_extension == ".eml"

    def parse(self, source: Path, evidence: Evidence) -> ParseResult:
        message = cast(
            EmailMessage, BytesParser(policy=policy.default).parsebytes(source.read_bytes())
        )
        attachments: list[ParsedAttachment] = []
        total_size = 0
        for index, part in enumerate(message.iter_attachments(), start=1):
            if index > self.max_attachments:
                raise EvidenceValidationError(
                    "EML_ATTACHMENT_LIMIT", "Email has too many attachments"
                )
            raw_content = part.get_payload(decode=True)
            content = raw_content if isinstance(raw_content, bytes) else b""
            total_size += len(content)
            if total_size > self.max_attachment_bytes:
                raise EvidenceValidationError(
                    "EML_ATTACHMENT_SIZE_LIMIT", "Email attachments are too large"
                )
            filename = safe_filename(part.get_filename() or f"attachment-{index}.bin")
            attachments.append(
                ParsedAttachment(
                    filename=filename,
                    content_type=part.get_content_type() or "application/octet-stream",
                    content=content,
                    metadata={"content_id": part.get("Content-ID"), "position": index},
                )
            )
        headers = {
            "from": str(message.get("From", "")),
            "to": str(message.get("To", "")),
            "cc": str(message.get("Cc", "")),
            "bcc": str(message.get("Bcc", "")),
            "date": str(message.get("Date", "")),
            "message_id": str(message.get("Message-ID", "")),
            "in_reply_to": str(message.get("In-Reply-To", "")),
        }
        return ParseResult(
            title=str(message.get("Subject", "")) or evidence.original_filename,
            text=_body_text(message),
            language=None,
            metadata={"headers": headers, "attachment_count": len(attachments)},
            attachments=tuple(attachments),
        )
