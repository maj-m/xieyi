import uuid
from email.message import EmailMessage
from pathlib import Path

from app.db.types import DocumentType, EvidenceSourceType
from app.models.evidence import Evidence
from app.parsers.eml import EmlParser


def test_eml_parser_normalizes_headers_body_and_attachments(tmp_path: Path) -> None:
    message = EmailMessage()
    message["From"] = "sender@example.test"
    message["To"] = "analyst@example.test"
    message["Subject"] = "测试邮件"
    message.set_content("邮件正文")
    message.add_attachment(
        b"attachment-data", maintype="text", subtype="plain", filename="note.txt"
    )
    source = tmp_path / "sample.eml"
    source.write_bytes(message.as_bytes())
    evidence = Evidence(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        original_filename="sample.eml",
        stored_filename="sample.eml",
        object_key="test/sample.eml",
        mime_type="message/rfc822",
        file_extension=".eml",
        file_size=source.stat().st_size,
        sha256="0" * 64,
        source_type=EvidenceSourceType.EMAIL,
        document_type=DocumentType.EMAIL,
        metadata_json={},
    )

    result = EmlParser().parse(source, evidence)

    assert result.title == "测试邮件"
    assert "邮件正文" in result.text
    assert result.metadata["attachment_count"] == 1
    assert result.attachments[0].filename == "note.txt"
    assert result.attachments[0].content == b"attachment-data"
