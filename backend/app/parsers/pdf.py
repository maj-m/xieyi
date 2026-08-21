"""PDF 解析器：逐页提取文本和文档属性，拒绝加密文件并限制最大页数。"""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.errors import EvidenceValidationError
from app.models.evidence import Evidence
from app.parsers.base import ParseResult
from app.parsers.limits import MAX_PDF_PAGES
from app.parsers.text import ensure_text_limit


class PdfParser:
    name = "pypdf"
    version = "1.0.0"

    def supports(self, evidence: Evidence) -> bool:
        return evidence.file_extension == ".pdf"

    def parse(self, source: Path, evidence: Evidence) -> ParseResult:
        try:
            reader = PdfReader(source, strict=True)
            if reader.is_encrypted:
                raise EvidenceValidationError("PDF_ENCRYPTED", "Encrypted PDF is not supported")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise EvidenceValidationError("PDF_PAGE_LIMIT", "PDF has too many pages")
            pages: list[str] = []
            pages_with_text = 0
            for index, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages_with_text += 1
                pages.append(f"## Page: {index}\n{text}")
            metadata = reader.metadata
        except PdfReadError as exc:
            raise EvidenceValidationError("PDF_INVALID", "PDF document is invalid") from exc
        return ParseResult(
            title=(metadata.title if metadata else None) or evidence.original_filename,
            text=ensure_text_limit("\n\n".join(pages)),
            language=None,
            metadata={
                "page_count": len(reader.pages),
                "pages_with_text": pages_with_text,
                "author": metadata.author if metadata else None,
                "subject": metadata.subject if metadata else None,
                "creator": metadata.creator if metadata else None,
                "ocr_recommended": pages_with_text == 0,
            },
        )
