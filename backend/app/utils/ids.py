from datetime import UTC, datetime


def format_case_no(sequence_value: int, now: datetime | None = None) -> str:
    if sequence_value < 1:
        raise ValueError("sequence_value must be positive")
    current = now or datetime.now(UTC)
    return f"CASE-{current.year}-{sequence_value:06d}"
