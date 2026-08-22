# 海关多智能体

当前先实现三个最小业务 Agent，代码位于 `customs.py`：

1. `extract_evidence_elements_agent`：提取主体、单号、金额、日期和带来源事实。
2. `associate_evidence_risk_agent`：关联邮件、发票、报关单和付款记录并判断风险。
3. `summarize_conclusion_agent`：检查冲突并生成提交人工复核的综合结论。

节点注册与流向统一在 `app/graph/workflow.py` 的 `build_case_workflow()` 中维护。
