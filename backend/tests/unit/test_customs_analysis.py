from app.analysis.customs import analyze_customs_evidence, format_customs_summary
from app.graph.state import EvidenceDocument


def test_customs_rule_links_evidence_and_detects_under_declaration() -> None:
    documents: list[EvidenceDocument] = [
        {
            "evidence_id": "email-1",
            "filename": "供应商邮件.eml",
            "document_type": "EMAIL",
            "title": "Final payment",
            "text": (
                "发票 INV-2026-0821，报关单 CN202608210001。合同实际总价为 105,000 美元，"
                "报关材料请按 68,000 美元准备申报。"
            ),
            "metadata": {},
        },
        {
            "evidence_id": "payment-1",
            "filename": "付款记录.csv",
            "document_type": "CSV",
            "title": "付款记录",
            "text": (
                "PAY-001\t2026-08-22\tINV-2026-0821\t68000.00\n"
                "PAY-002\t2026-08-25\tINV-2026-0821\t37000.00"
            ),
            "metadata": {},
        },
    ]

    result = analyze_customs_evidence(documents)

    assert result["risk_level"] == "HIGH"
    assert result["declared_amount_usd"] == 68000.0
    assert result["actual_amount_usd"] == 105000.0
    assert result["payment_total_usd"] == 105000.0
    assert result["difference_usd"] == 37000.0
    assert result["suspicious_instruction"] is True
    assert "HIGH" in format_customs_summary(result)
