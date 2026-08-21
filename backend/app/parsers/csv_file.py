"""CSV 解析器：识别编码和分隔符，将表格转换为可供检索及 Agent 使用的制表文本。"""

import csv
import io
from pathlib import Path

from app.errors import EvidenceValidationError
from app.models.evidence import Evidence
from app.parsers.base import ParseResult
from app.parsers.limits import MAX_SPREADSHEET_CELLS, MAX_SPREADSHEET_ROWS
from app.parsers.text import decode_text, ensure_text_limit


class CsvParser:
    name = "builtin-csv"
    version = "1.0.0"

    def supports(self, evidence: Evidence) -> bool:
        return evidence.file_extension == ".csv"

    def parse(self, source: Path, evidence: Evidence) -> ParseResult:
        content, encoding = decode_text(source.read_bytes())
        sample = content[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows: list[str] = []
        cell_count = 0
        column_count = 0
        for row_number, row in enumerate(csv.reader(io.StringIO(content), dialect), start=1):
            if row_number > MAX_SPREADSHEET_ROWS:
                raise EvidenceValidationError("CSV_ROW_LIMIT", "CSV contains too many rows")
            cell_count += len(row)
            column_count = max(column_count, len(row))
            if cell_count > MAX_SPREADSHEET_CELLS:
                raise EvidenceValidationError("CSV_CELL_LIMIT", "CSV contains too many cells")
            rows.append("\t".join(value.strip() for value in row))
        text = ensure_text_limit("\n".join(rows))
        return ParseResult(
            title=evidence.original_filename,
            text=text,
            language=None,
            metadata={
                "encoding": encoding,
                "delimiter": dialect.delimiter,
                "row_count": len(rows),
                "column_count": column_count,
                "cell_count": cell_count,
            },
        )
