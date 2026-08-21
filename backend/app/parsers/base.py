from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.models.evidence import Evidence


@dataclass(frozen=True, slots=True)
class ParsedAttachment:
    filename: str
    content_type: str
    content: bytes
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class ParseResult:
    title: str | None
    text: str
    language: str | None
    metadata: dict[str, object]
    attachments: tuple[ParsedAttachment, ...] = ()


class EvidenceParser(Protocol):
    name: str
    version: str

    def supports(self, evidence: Evidence) -> bool: ...

    def parse(self, source: Path, evidence: Evidence) -> ParseResult: ...
