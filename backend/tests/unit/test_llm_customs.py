import json

import pytest

from app.analysis import llm_customs
from app.graph.state import EvidenceDocument


@pytest.mark.asyncio
async def test_llm_customs_returns_validated_auditable_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, object]:
        assert url == "http://llm.test/v1/chat/completions"
        assert headers["Authorization"] == "Bearer secret"
        assert payload["response_format"] == {"type": "json_object"}
        assert timeout_seconds == 30
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "risk_level": "HIGH",
                                "declaration_numbers": ["CN202608210001"],
                                "invoice_numbers": ["INV-2026-0821"],
                                "declared_amount_usd": 68000,
                                "actual_amount_usd": 105000,
                                "payment_total_usd": 105000,
                                "suspicious_instruction": "邮件明确要求按较低金额申报",
                                "findings": [
                                    {
                                        "finding": "申报金额低于实际付款金额",
                                        "evidence_ids": ["email-1", "unknown"],
                                    }
                                ],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(llm_customs, "_post_json", fake_post)
    documents: list[EvidenceDocument] = [
        {
            "evidence_id": "email-1",
            "filename": "供应商邮件.eml",
            "document_type": "EMAIL",
            "title": "付款通知",
            "text": "实际总价 105000 美元，按 68000 美元申报。",
            "metadata": {},
        }
    ]

    result = await llm_customs.analyze_customs_with_llm(
        documents,
        base_url="http://llm.test/v1",
        api_key="secret",
        model="test-model",
        timeout_seconds=30,
        max_input_characters=1000,
    )

    assert result["analysis_method"] == "LLM"
    assert result["difference_usd"] == 37000
    assert result["suspicious_instruction"] is True
    assert result["evidence_reasons"] == [
        {"finding": "申报金额低于实际付款金额", "evidence_ids": ["email-1"]}
    ]
    assert result["llm_trace"]["model"] == "test-model"  # type: ignore[index]
    assert result["llm_trace"]["raw_response"]  # type: ignore[index]
