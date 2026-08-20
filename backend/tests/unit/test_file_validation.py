import pytest

from app.errors import EvidenceValidationError
from app.security.file_validation import FileValidator, safe_filename


def test_safe_filename_removes_path_and_unsafe_characters() -> None:
    assert safe_filename("../../案件/evil name?.PDF") == "evil_name.pdf"
    assert safe_filename("..\\..\\invoice.csv") == "invoice.csv"


def test_validator_checks_extension_mime_empty_and_size() -> None:
    validator = FileValidator((".eml", ".csv"), max_size_bytes=10)
    assert validator.validate_metadata("mail.eml", "message/rfc822") == ("mail.eml", ".eml")
    with pytest.raises(EvidenceValidationError, match="Unsupported"):
        validator.validate_metadata("payload.exe", "application/octet-stream")
    with pytest.raises(EvidenceValidationError, match="MIME"):
        validator.validate_metadata("bank.csv", "image/png")
    with pytest.raises(EvidenceValidationError, match="empty"):
        validator.validate_size(0)
    with pytest.raises(EvidenceValidationError, match="large"):
        validator.validate_size(11)
