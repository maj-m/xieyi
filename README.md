# 鲸鲨 MAS

鲸鲨 MAS 是面向海关缉私案件研判的多智能体系统。当前已实现后端数据底座，以及第二阶段的
最小 LangGraph 研判链路：案件准备、人工复核暂停、恢复和完成。真实 LLM、业务 Agent、MCP、
LangSmith、OCR 与业务研判算法仍不在当前范围内。

## 技术栈

Python 3.12+、FastAPI、Pydantic v2、SQLAlchemy 2 Async、asyncpg、PostgreSQL 16、
Alembic、MinIO、LangGraph、PostgreSQL Checkpointer、pytest、ruff、mypy 和 Docker Compose。

## 目录

- `backend/app/api`：HTTP 接口
- `backend/app/services`：业务与跨存储一致性逻辑
- `backend/app/repositories`：异步数据库访问
- `backend/app/storage`：对象存储抽象和 MinIO 实现
- `backend/app/graph`：最小 `CaseState`、StateGraph 和 interrupt 节点
- `backend/alembic`：正式数据库迁移
- `backend/tests`：单元、API、Repository、集成测试
- `docs`：架构、数据库、开发和进度文档
- `demo_data`：全虚构验收文件

## 启动

要求 Docker 及 Docker Compose v2。默认开发凭据仅用于本机 Compose；生产环境必须通过环境变量
替换。可先复制 `.env.example` 为 `.env` 并修改所有 `change-me` 值，也可使用 Compose 的开发默认值。

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/ready
```

Backend 启动时执行 `alembic upgrade head`，不会使用 `metadata.create_all()` 代替迁移。

本地开发：

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

也提供 `make up/down/logs/migrate/test/lint/format/typecheck`。

## 环境变量

完整清单见 `.env.example`。核心项为 `DATABASE_URL`、`MINIO_ENDPOINT`、
`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_BUCKET`、`MAX_UPLOAD_SIZE_MB`、
`ALLOWED_FILE_EXTENSIONS` 和 `AUDIT_HASH_CHAIN_ENABLED`。密钥不得写入代码或镜像。

## API 示例

```bash
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Content-Type: application/json" \
  -d '{"name":"测试低报价格案件","description":"第一阶段虚构测试案件"}'

curl -X POST http://localhost:8000/api/v1/cases/{case_id}/evidence \
  -F "file=@demo_data/sample.eml;type=message/rfc822" \
  -F "source_type=EMAIL"

curl http://localhost:8000/api/v1/cases/{case_id}/audit
curl http://localhost:8000/api/v1/cases/{case_id}/audit/verify
```

同一案件再次上传相同 SHA-256 文件返回 `409 DUPLICATE_EVIDENCE`。错误统一返回
`error.code/message/request_id`，响应头同时包含 `X-Request-ID`。

## 最小研判链路

启动流程后会在人工复核节点暂停：

```bash
curl -X POST http://localhost:8000/api/v1/cases/{case_id}/workflows \
  -H "Content-Type: application/json" \
  -d '{"analysis_scope":"minimal_case_review"}'

curl http://localhost:8000/api/v1/workflows/{thread_id}

curl -X POST http://localhost:8000/api/v1/workflows/{thread_id}/resume \
  -H "Content-Type: application/json" \
  -d '{"approved":true,"comment":"同意继续"}'
```

`thread_id` 必须稳定保存。Checkpoint 表由官方 PostgreSQL checkpointer 的 `setup()` 管理，
Backend 每次启动都会安全地检查其内部 migration。
