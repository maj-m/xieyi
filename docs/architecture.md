# 第一阶段架构

```mermaid
flowchart LR
    Client --> API[FastAPI API]
    API --> Service[Service]
    Service --> Repository[Repository]
    Repository --> PostgreSQL[(PostgreSQL)]
    Service --> Storage[ObjectStorage Protocol]
    Storage --> MinIO[(MinIO)]
    Service --> Audit[AuditService]
    Audit --> Repository
    API --> Workflow[WorkflowService]
    Workflow --> Graph[LangGraph StateGraph]
    Graph --> Checkpoint[(PostgreSQL Checkpoints)]
```

HTTP 层只做输入输出转换。Service 承担业务规则、事务边界和 PostgreSQL/MinIO 之间的显式补偿；
Repository 只负责数据库访问；`ObjectStorage` 隔离 MinIO SDK。证据对象路径完全由服务端构造：
`cases/{case_id}/evidence/{evidence_id}/{safe_filename}`。

MinIO 写入成功而 DB 操作失败时，服务尝试删除对象；补偿失败会记录明确错误，未来可由孤儿对象清理任务
对账。这不是跨系统 ACID 事务。

最小图为 `prepare_case → human_review(interrupt) → finalize_case`。图状态只包含案件标识、证据数量、
预研判摘要和人工决定，不保存证据正文。`thread_id` 用于跨请求和服务重启定位 checkpoint。

`app/agents` 仍只是扩展边界，不包含业务 Agent 伪实现。
