# 开发说明

## 工作流

1. 安装 Python 3.12+、Docker、uv。
2. 在 `backend` 执行 `uv sync --extra dev`。
3. 用 `docker compose up -d postgres minio minio-init` 启动依赖。
4. 设置本地 `DATABASE_URL` 与 MinIO 环境变量，执行 `uv run alembic upgrade head`。
5. 执行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、
   `uv run mypy app`。

集成测试使用真实 PostgreSQL 和 MinIO，测试替身只用于隔离的单元测试。测试数据均在 `demo_data`，
不包含真实案件信息。

Windows 本地测试使用 Selector event loop，因为 Psycopg 异步连接不支持 Windows 默认的 Proactor
event loop；Linux 和 Docker 使用平台默认事件循环。

## 安全与日志

上传同时校验扩展名、声明 MIME、大小、空文件和清洗后的文件名；声明 MIME 不是唯一信任来源，未来可
增加 magic bytes。日志不得输出文件正文、银行流水、邮件正文和任何密钥。

## 下一阶段边界

当前已经验证最小 StateGraph、PostgreSQL checkpointer 和 interrupt/resume。下一阶段应先接入一个
真实但低风险的研判节点和相应评测，再决定 Agent 拆分数量，不直接照搬 23 角色。
