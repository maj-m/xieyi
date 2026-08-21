"""海关价格申报风险规则：关联报关单、发票、付款和邮件中的金额及标识。"""

import re
from decimal import Decimal

from app.graph.state import EvidenceDocument

DECLARATION_RE = re.compile(r"\bCN\d{12}\b", re.IGNORECASE)
INVOICE_RE = re.compile(r"\bINV-\d{4}-\d{4}\b", re.IGNORECASE)
AMOUNT_RE = r"([0-9][0-9,]*(?:\.\d+)?)"


def _amounts_after(text: str, keywords: tuple[str, ...]) -> list[Decimal]:
    values: list[Decimal] = []
    for keyword in keywords:
        for match in re.finditer(rf"(?:{keyword}).{{0,60}}?{AMOUNT_RE}", text, re.IGNORECASE):
            values.append(Decimal(match.group(1).replace(",", "")))
    return values


def _payment_total(documents: list[EvidenceDocument]) -> Decimal | None:
    payments: list[Decimal] = []
    for document in documents:
        if not document["filename"].lower().endswith(".csv"):
            continue
        for line in document["text"].splitlines():
            if not line.startswith("PAY-"):
                continue
            numbers = re.findall(AMOUNT_RE, line.replace("\t", " "))
            if numbers:
                payments.append(Decimal(numbers[-1].replace(",", "")))
    return sum(payments, Decimal()) if payments else None


def analyze_customs_evidence(documents: list[EvidenceDocument]) -> dict[str, object]:
    combined = "\n".join(document["text"] for document in documents)
    declaration_numbers = sorted(set(DECLARATION_RE.findall(combined)))
    invoice_numbers = sorted(set(INVOICE_RE.findall(combined)))
    declared_values = _amounts_after(
        combined, (r"申报总价", r"申报金额", r"报关材料.{0,20}(?:按|按照)")
    )
    actual_values = _amounts_after(
        combined, (r"实际总价", r"合同实际总价", r"Total Amount \(USD\)")
    )
    payment_total = _payment_total(documents)
    declared_amount = min(declared_values) if declared_values else None
    actual_candidates = actual_values + ([payment_total] if payment_total is not None else [])
    actual_amount = max(actual_candidates) if actual_candidates else None
    difference = (
        actual_amount - declared_amount
        if actual_amount is not None and declared_amount is not None
        else None
    )
    suspicious_instruction = bool(
        re.search(r"报关材料.{0,30}(?:按|按照).{0,20}(?:准备|申报)", combined, re.DOTALL)
    )
    risk_level = (
        "HIGH"
        if difference is not None and difference > 0 and suspicious_instruction
        else "MEDIUM"
        if difference is not None and difference > 0
        else "LOW"
    )
    findings: list[str] = []
    if difference is not None and difference > 0:
        findings.append(f"实际成交或付款金额高于申报金额 {difference:,.2f} 美元")
    if suspicious_instruction:
        findings.append("邮件中存在按较低金额准备报关材料的明确表述")
    if declaration_numbers and invoice_numbers:
        findings.append("报关单号与发票号可在多份证据间建立关联")
    return {
        "risk_level": risk_level,
        "declaration_numbers": declaration_numbers,
        "invoice_numbers": invoice_numbers,
        "declared_amount_usd": float(declared_amount) if declared_amount is not None else None,
        "actual_amount_usd": float(actual_amount) if actual_amount is not None else None,
        "payment_total_usd": float(payment_total) if payment_total is not None else None,
        "difference_usd": float(difference) if difference is not None else None,
        "suspicious_instruction": suspicious_instruction,
        "findings": findings,
        "evidence_refs": [
            {
                "evidence_id": document["evidence_id"],
                "filename": document["filename"],
                "document_type": document["document_type"],
            }
            for document in documents
        ],
        "rule_version": "customs-price-risk-v1",
    }


def format_customs_summary(analysis: dict[str, object]) -> str:
    difference = analysis.get("difference_usd")
    findings = analysis.get("findings", [])
    detail = "；".join(str(item) for item in findings) if isinstance(findings, list) else ""
    amount = f"，价差 {float(difference):,.2f} 美元" if isinstance(difference, int | float) else ""
    return (
        f"海关价格申报风险等级：{analysis['risk_level']}{amount}。"
        f"{detail or '当前证据未发现明确价格差异。'}"
    )
