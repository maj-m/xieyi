# 最小案件研判图

当前只实现一条确定性链路：

```text
prepare_case → human_review(interrupt) → finalize_case
```

`thread_id` 是持久恢复游标，checkpoint 由官方 `AsyncPostgresSaver` 写入 PostgreSQL。
Backend 重启后，调用状态接口读取原 checkpoint，再用同一 `thread_id` 提交
`Command(resume=...)` 即可继续。

本阶段不调用 LLM，不实现 23 个 Agent，也不接 MCP、LangSmith 或业务分析算法。
