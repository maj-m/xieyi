"""解析器注册表：根据证据类型选择具体解析器，是后续扩展 PDF、Office 和 OCR 的统一入口。"""

from app.models.evidence import Evidence
from app.parsers.base import EvidenceParser
from app.parsers.csv_file import CsvParser
from app.parsers.eml import EmlParser
from app.parsers.pdf import PdfParser
from app.parsers.spreadsheet import SpreadsheetParser
from app.parsers.text import TextParser
from app.parsers.word import DocxParser


class ParserRegistry:
    def __init__(self, parsers: tuple[EvidenceParser, ...]) -> None:
        self.parsers = parsers

    def find(self, evidence: Evidence) -> EvidenceParser | None:
        return next((parser for parser in self.parsers if parser.supports(evidence)), None)


def build_parser_registry() -> ParserRegistry:
    return ParserRegistry(
        (EmlParser(), TextParser(), CsvParser(), SpreadsheetParser(), DocxParser(), PdfParser())
    )
