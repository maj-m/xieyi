from datetime import UTC, datetime

import pytest

from app.utils.ids import format_case_no


def test_case_number_generator() -> None:
    assert format_case_no(42, datetime(2026, 8, 18, tzinfo=UTC)) == "CASE-2026-000042"
    with pytest.raises(ValueError, match="positive"):
        format_case_no(0)
