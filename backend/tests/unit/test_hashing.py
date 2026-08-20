import hashlib
from pathlib import Path

from app.utils.hashing import sha256_file


def test_sha256_file_streams_expected_digest(tmp_path: Path) -> None:
    content = b"whale-mas-evidence" * 1000
    evidence = tmp_path / "sample.eml"
    evidence.write_bytes(content)
    assert sha256_file(evidence, chunk_size=31) == hashlib.sha256(content).hexdigest()
