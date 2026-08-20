# 最小案件研判图

当前实现一条带人工复核多分支的确定性链路：

```text
prepare_case → human_review(interrupt)
  ├─ APPROVE          → finalize_case → COMPLETED
  ├─ REANALYZE        → reanalyze_case → human_review（最多 3 轮）
  ├─ REQUEST_EVIDENCE → mark_evidence_required → await_evidence(interrupt)
  │                     → EVIDENCE_READY → prepare_case → human_review
  └─ CANCEL           → cancel_case → CANCELLED
```

每次复核保存决定、意见、复核人、UTC 时间和轮次。旧版 `approved: true/false` 请求仍兼容，
分别映射为 `APPROVE/CANCEL`。当前复核记录属于 LangGraph state/checkpoint，尚未拆分为独立业务表。

`thread_id` 是持久恢复游标，checkpoint 由官方 `AsyncPostgresSaver` 写入 PostgreSQL。
Backend 重启后，调用状态接口读取原 checkpoint，再用同一 `thread_id` 提交
`Command(resume=...)` 即可继续。`WAITING_REVIEW` 和 `WAITING_EVIDENCE` 都是可恢复暂停状态。

本阶段不调用 LLM，不实现 23 个 Agent，也不接 MCP、LangSmith 或业务分析算法。
